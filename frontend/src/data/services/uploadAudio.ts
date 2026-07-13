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
