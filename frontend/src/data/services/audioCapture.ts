/**
 * 실시간 오디오 캡처 (플랫폼 분기의 네이티브 스텁).
 *
 * 웹: audioCapture.web.ts 가 실제 구현(마이크 → 16kHz mono WAV 3초 청크).
 * 네이티브: 실시간 STT는 온디바이스 음성인식(텍스트) 경로를 쓰므로 오디오 캡처는 미사용.
 *           (useCallSession이 web에서만 createAudioCapture를 호출하지만, 임포트 해석을 위해 스텁을 둔다)
 */

/** 캡처된 오디오 청크 1개 (WAV 컨테이너) */
export interface AudioChunk {
  /** WAV 바이트 (RIFF 헤더 포함) */
  bytes: ArrayBuffer;
  /** WAV 바이트의 base64 (audio_chunk 전송용) */
  base64: string;
  /** 1부터 증가하는 청크 순번 */
  chunkIndex: number;
}

export interface AudioCaptureService {
  start(): Promise<void>;
  stop(): void;
  /** 아직 청크 길이(3초)를 못 채운 마지막 버퍼를 즉시 한 청크로 내보낸다(종료 시 마지막 발화 누락 방지). */
  flushFinal(): void;
  onChunk(cb: (c: AudioChunk) => void): void;
  onError(cb: (msg: string) => void): void;
}

export function createAudioCapture(): AudioCaptureService {
  return {
    async start() {},
    stop() {},
    flushFinal() {},
    onChunk() {},
    onError(cb) {
      cb('실시간 오디오 캡처는 웹에서만 지원됩니다.');
    },
  };
}
