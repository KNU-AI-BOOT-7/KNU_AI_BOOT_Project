/**
 * 파일 분석 — 웹(브라우저) 업로드 구현.
 *
 * 브라우저에서는 네이티브의 {uri,name,type} 형식이 통하지 않는다.
 * DocumentPicker가 준 uri(blob:/data:/http:)를 실제 Blob으로 받아 File로 감싼 뒤
 * FormData에 append 해야 서버가 정상적인 multipart 파일로 인식한다.
 * (Metro가 웹 번들에서 uploadAudio.ts 대신 이 파일을 우선 해석한다)
 */
import { BASE_URL_HTTP } from '@/core/config/env';
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

/**
 * 실시간 통화 종료 시, 세션 전체 녹음(WAV Blob)을 통째로 분석 API에 올려 재전사한다.
 * 청크별 전사와 달리 통화 전체를 한 번에 보므로 화자 A/B가 정확하게 분리된다.
 */
export async function analyzeSessionAudio(audio: Blob): Promise<AudioAnalysisResult> {
  const uploadFile = new File([audio], 'session.wav', { type: 'audio/wav' });
  const form = new FormData();
  form.append('file', uploadFile);

  const res = await fetch(ANALYZE_AUDIO_URL, {
    method: 'POST',
    body: form,
  });
  return parseAnalyzeResponse(res);
}

/**
 * 기존 통화 로그(logId)에 세션 전체 녹음을 재전사해 덮어쓴다.
 * 새 로그를 만들지 않고 실시간 세션 로그 하나에 정확한 화자 A/B 결과를 반영한다.
 */
export async function retranscribeSessionAudio(logId: number, audio: Blob): Promise<AudioAnalysisResult> {
  const uploadFile = new File([audio], 'session.wav', { type: 'audio/wav' });
  const form = new FormData();
  form.append('file', uploadFile);

  const res = await fetch(`${BASE_URL_HTTP}/calls/${logId}/retranscribe-audio`, {
    method: 'POST',
    body: form,
  });
  return parseAnalyzeResponse(res);
}
