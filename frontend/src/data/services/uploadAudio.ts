/**
 * 파일 분석 — 네이티브(iOS/Android) 업로드 구현.
 *
 * React Native의 FormData는 파일을 {uri, name, type} 객체로 append 한다.
 * (웹 구현은 uploadAudio.web.ts — Metro가 웹 번들에서 자동으로 우선 해석)
 */
import {
  ANALYZE_AUDIO_URL,
  guessMime,
  parseAnalyzeResponse,
  type AudioAnalysisResult,
  type PickedAudio,
} from './uploadAudio.shared';

export type { AudioAnalysisResult, AudioSegment, PickedAudio } from './uploadAudio.shared';

export async function analyzeAudioFile(file: PickedAudio): Promise<AudioAnalysisResult> {
  const form = new FormData();
  form.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.mime ?? guessMime(file.name),
  } as unknown as Blob);

  const res = await fetch(ANALYZE_AUDIO_URL, {
    method: 'POST',
    body: form,
  });
  return parseAnalyzeResponse(res);
}

/** 세션 전체 오디오 재전사는 웹 오디오 캡처 경로에서만 사용된다(네이티브는 온디바이스 STT). */
export async function analyzeSessionAudio(_audio: Blob): Promise<AudioAnalysisResult> {
  throw new Error('세션 오디오 재전사는 웹에서만 지원됩니다.');
}

export async function retranscribeSessionAudio(_logId: number, _audio: Blob): Promise<AudioAnalysisResult> {
  throw new Error('세션 오디오 재전사는 웹에서만 지원됩니다.');
}
