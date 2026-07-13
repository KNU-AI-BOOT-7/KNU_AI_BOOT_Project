/**
 * 실시간 오디오 캡처 — 웹(브라우저) 구현.
 *
 * 파이프라인: getUserMedia(마이크) → AudioContext(16kHz) → AudioWorklet(PCM 추출)
 *   → Float32 PCM 누적 → 약 3초마다 16-bit WAV로 인코딩 → onChunk 콜백.
 *
 * 백엔드로는 WAV(16kHz·mono·16-bit) 청크를 그대로 보낸다(wsService가 audio_chunk로 전송).
 * WAV는 자기설명적(헤더에 샘플레이트 포함)이라, 브라우저가 16kHz 강제를 무시해도 백엔드가 헤더로 해석 가능.
 */
import { Buffer } from 'buffer';
import type { AudioCaptureService, AudioChunk } from './audioCapture';

export type { AudioCaptureService, AudioChunk } from './audioCapture';

const TARGET_RATE = 16000;
const CHANNELS = 1;
// 고정 길이로 자르면 경계가 단어 한가운데 떨어져 오인식이 생기고("금융지원센터" →
// "금융지주"+"더"), 겹쳐 보내면(overlap) 같은 말이 두 번 전사돼 중복/파편이 생긴다.
// 그래서 고정 간격 대신 "말이 잠깐 끊긴 지점(무음)"에서 청크를 자른다:
//  - 최소 MIN_CHUNK_SECONDS는 쌓고, 이후 꼬리 SILENCE_SECONDS 구간이 조용하면 flush
//  - 무음이 안 와도 MAX_CHUNK_SECONDS가 되면 강제 flush (상한)
// 경계가 문장 사이 쉼에 떨어지므로 단어가 잘리지 않고, 겹침도 없어 중복이 원천 차단된다.
const MIN_CHUNK_SECONDS = 3;
const MAX_CHUNK_SECONDS = 10;
const SILENCE_SECONDS = 0.3;
const SILENCE_RMS = 0.01;

/* AudioWorklet 프로세서: 입력 PCM 프레임(128 샘플)을 메인 스레드로 전달만 한다.
   별도 파일 없이 Blob URL로 로드(Expo 웹 번들에서 워클릿 파일 서빙 회피). */
const WORKLET_CODE = `
class PCMCapture extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      // 렌더 버퍼는 재사용되므로 복사해서 전달
      this.port.postMessage(input[0].slice(0));
    }
    return true;
  }
}
registerProcessor('pcm-capture', PCMCapture);
`;

/** Float32 PCM(-1~1) → 16-bit WAV(ArrayBuffer) */
function floatToWav(float32: Float32Array, sampleRate: number): ArrayBuffer {
  const n = float32.length;
  const buffer = new ArrayBuffer(44 + n * 2);
  const view = new DataView(buffer);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + n * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); // fmt 청크 크기
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, CHANNELS, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * CHANNELS * 2, true); // byte rate
  view.setUint16(32, CHANNELS * 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, 'data');
  view.setUint32(40, n * 2, true);
  let off = 44;
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }
  return buffer;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
class WebAudioCapture implements AudioCaptureService {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private frames: Float32Array[] = [];
  private frameLen = 0;
  private chunkIndex = 0;
  private chunkCb: ((c: AudioChunk) => void) | null = null;
  private errCb: ((m: string) => void) | null = null;
  private stopped = false;
  private workletUrl: string | null = null;
  private rate = 0; // 실제 캡처 샘플레이트(마지막 flush에 사용)

  onChunk(cb: (c: AudioChunk) => void) {
    this.chunkCb = cb;
  }
  onError(cb: (m: string) => void) {
    this.errCb = cb;
  }

  async start() {
    this.stopped = false;
    // 1) 마이크 (내장 마이크 품질 보정: 에코 제거/잡음 억제/자동 게인)
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        } as MediaTrackConstraints,
      });
    } catch {
      this.errCb?.('마이크 접근에 실패했습니다. 브라우저 마이크 권한을 허용해 주세요.');
      return;
    }
    if (this.stopped) {
      this.stop();
      return;
    }

    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!Ctx) {
      this.errCb?.('이 브라우저는 오디오 캡처를 지원하지 않습니다. (크롬/엣지 권장)');
      return;
    }

    // 2) 16kHz AudioContext로 그래프 구성 시도 → 실패 시 기본 레이트로 폴백.
    //    (일부 브라우저는 마이크 native 레이트와 다른 ctx에 createMediaStreamSource 연결을 거부)
    //    WAV 헤더가 실제 레이트를 기록하므로 폴백해도 백엔드는 정상 해석한다.
    const ok = (await this.setupGraph(Ctx, TARGET_RATE)) || (await this.setupGraph(Ctx, 0));
    if (!ok) {
      if (!this.stopped) this.errCb?.('오디오 캡처 초기화에 실패했습니다. (크롬/엣지 권장)');
      return;
    }
  }

  /** 주어진 샘플레이트로 ctx+worklet+그래프를 구성. 성공하면 true. (rate=0이면 기본 레이트) */
  private async setupGraph(Ctx: any, rate: number): Promise<boolean> {
    try {
      this.ctx = rate > 0 ? new Ctx({ sampleRate: rate }) : new Ctx();
      const actualRate = this.ctx!.sampleRate;
      this.rate = actualRate;
      const minChunkSamples = Math.floor(actualRate * MIN_CHUNK_SECONDS);
      const maxChunkSamples = Math.floor(actualRate * MAX_CHUNK_SECONDS);
      const silenceSamples = Math.floor(actualRate * SILENCE_SECONDS);

      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
      this.workletUrl = URL.createObjectURL(blob);
      await this.ctx!.audioWorklet.addModule(this.workletUrl);
      if (this.stopped) {
        this.stop();
        return true; // 중단됨: 더 진행하지 않음
      }

      // 그래프: source → worklet → (무음 gain) → destination
      this.source = this.ctx!.createMediaStreamSource(this.stream!);
      this.node = new AudioWorkletNode(this.ctx!, 'pcm-capture');
      this.node.port.onmessage = (e: MessageEvent) => {
        const frame = e.data as Float32Array;
        this.frames.push(frame);
        this.frameLen += frame.length;
        // 최소 길이를 넘긴 뒤 꼬리가 조용해지면(말이 끊긴 지점) flush.
        // 무음이 계속 안 오면 상한(MAX)에서 강제 flush.
        if (
          this.frameLen >= maxChunkSamples ||
          (this.frameLen >= minChunkSamples && this.tailIsSilent(silenceSamples))
        ) {
          this.flush(actualRate);
        }
      };
      this.source.connect(this.node);
      // 워클릿 process()가 계속 호출되도록 destination까지 연결하되, gain 0으로 소리 재생은 막는다.
      const silent = this.ctx!.createGain();
      silent.gain.value = 0;
      this.node.connect(silent);
      silent.connect(this.ctx!.destination);

      if (this.ctx!.state === 'suspended') {
        try {
          await this.ctx!.resume();
        } catch {
          /* ignore */
        }
      }
      return true;
    } catch {
      // 이 레이트로 실패 → 정리하고 폴백 시도
      try {
        this.source?.disconnect();
        this.node?.disconnect();
        void this.ctx?.close();
      } catch {
        /* ignore */
      }
      if (this.workletUrl) {
        URL.revokeObjectURL(this.workletUrl);
        this.workletUrl = null;
      }
      this.ctx = null;
      this.source = null;
      this.node = null;
      return false;
    }
  }

  /** 뒤쪽 silenceSamples 구간의 RMS가 임계값보다 작으면(말이 끊긴 상태) true. */
  private tailIsSilent(silenceSamples: number): boolean {
    let need = silenceSamples;
    let sumSq = 0;
    let count = 0;
    for (let i = this.frames.length - 1; i >= 0 && need > 0; i--) {
      const f = this.frames[i];
      const take = Math.min(need, f.length);
      for (let j = f.length - take; j < f.length; j++) {
        sumSq += f[j] * f[j];
        count++;
      }
      need -= take;
    }
    if (count < silenceSamples) return false; // 아직 무음 판정에 필요한 만큼 안 쌓임
    return Math.sqrt(sumSq / count) < SILENCE_RMS;
  }

  /** 누적 버퍼 전체를 WAV 청크 하나로 방출. 겹침 없이 무음 경계에서 통째로 자른다. */
  private flush(rate: number) {
    const merged = new Float32Array(this.frameLen);
    let off = 0;
    for (const f of this.frames) {
      merged.set(f, off);
      off += f.length;
    }
    this.frames = [];
    this.frameLen = 0;

    // 통째로 무음인 청크(아무도 말하지 않는 구간)는 전사 가치가 없으므로 버린다.
    // 안 버리면 침묵 중에도 min 길이마다 무음 청크가 백엔드(STT API)로 계속 나간다.
    let sumSq = 0;
    for (let i = 0; i < merged.length; i++) sumSq += merged[i] * merged[i];
    if (merged.length > 0 && Math.sqrt(sumSq / merged.length) < SILENCE_RMS) return;

    const bytes = floatToWav(merged, rate);
    const base64 = Buffer.from(new Uint8Array(bytes)).toString('base64');
    this.chunkIndex += 1;
    this.chunkCb?.({ bytes, base64, chunkIndex: this.chunkIndex });
  }

  /** 아직 최소 길이를 못 채운 남은 버퍼를 한 청크로 즉시 방출(종료 직전 마지막 발화 보존). */
  flushFinal() {
    if (this.frameLen <= 0 || this.rate <= 0) return;
    const merged = new Float32Array(this.frameLen);
    let off = 0;
    for (const f of this.frames) {
      merged.set(f, off);
      off += f.length;
    }
    this.frames = [];
    this.frameLen = 0;
    // 너무 짧은 조각(0.4초 미만)은 전사 가치가 없어 건너뛴다.
    if (merged.length < this.rate * 0.4) return;
    // 남은 버퍼가 통째로 무음이면(종료 직전 침묵) 보내지 않는다.
    let sumSq = 0;
    for (let i = 0; i < merged.length; i++) sumSq += merged[i] * merged[i];
    if (Math.sqrt(sumSq / merged.length) < SILENCE_RMS) return;
    const bytes = floatToWav(merged, this.rate);
    const base64 = Buffer.from(new Uint8Array(bytes)).toString('base64');
    this.chunkIndex += 1;
    this.chunkCb?.({ bytes, base64, chunkIndex: this.chunkIndex });
  }

  stop() {
    this.stopped = true;
    try {
      this.source?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      this.node?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      this.stream?.getTracks().forEach((t) => t.stop());
    } catch {
      /* ignore */
    }
    try {
      void this.ctx?.close();
    } catch {
      /* ignore */
    }
    if (this.workletUrl) {
      URL.revokeObjectURL(this.workletUrl);
      this.workletUrl = null;
    }
    this.frames = [];
    this.frameLen = 0;
  }
}

export function createAudioCapture(): AudioCaptureService {
  return new WebAudioCapture();
}
