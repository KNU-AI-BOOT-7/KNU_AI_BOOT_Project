/**
 * 파일 분석 — 웹(브라우저) 업로드 구현.
 *
 * 브라우저에서는 네이티브의 {uri,name,type} 형식이 통하지 않는다.
 * DocumentPicker가 준 uri(blob:/data:/http:)를 실제 Blob으로 받아 File로 감싼 뒤
 * FormData에 append 해야 서버가 정상적인 multipart 파일로 인식한다.
 * (Metro가 웹 번들에서 uploadAudio.ts 대신 이 파일을 우선 해석한다)
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
  // 선택한 파일의 uri를 실제 바이너리(Blob)로 로드한다.
  const srcRes = await fetch(file.uri);
  if (!srcRes.ok) {
    throw new Error('선택한 파일을 읽을 수 없습니다. 다시 선택해 주세요.');
  }
  const blob = await srcRes.blob();
  const type = file.mime || blob.type || guessMime(file.name);
  const uploadFile = new File([blob], file.name, { type });

  const form = new FormData();
  form.append('file', uploadFile);

  const res = await fetch(ANALYZE_AUDIO_URL, {
    method: 'POST',
    body: form,
  });
  return parseAnalyzeResponse(res);
}
