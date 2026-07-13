/**
 * 파일 분석 공용 로직 (플랫폼 무관).
 *
 * 업로드 자체는 웹(실제 File/Blob)과 네이티브({uri,name,type})가 달라서
 * uploadAudio.ts(네이티브) / uploadAudio.web.ts(웹) 로 분기하고,
 * 엔드포인트 URL · MIME 추론 · 응답 파싱은 이 모듈을 공유한다.
 *
 * 백엔드: POST {BASE_URL_HTTP}/calls/analyze-audio (multipart, field=file)
 * 응답(API_SPEC 6. 녹음 파일 분석):
 *   { log_id, file_name, segments:[{chunk_id,start_time(초),end_time(초),speaker,text}],
 *     is_phishing, risk_score, risk_level, phishing_type, matched_patterns, core_evidence, notification }
 */
import { ANALYZE_AUDIO_PATH, BASE_URL_HTTP } from '@/core/config/env';
import type { BackendRiskLevel } from '@/data/models/types';

/** 선택한 오디오 파일 정보 (DocumentPicker asset에서 추출) */
export interface PickedAudio {
  uri: string;
  name: string;
  mime?: string;
}

/** 발화 세그먼트 (start/end 단위: 초). 파일 분석은 화자분리 없음 → speaker='speaker_a' */
export interface AudioSegment {
  speaker: string;
  text: string;
  start: number; // 초
  end: number; // 초
}

/** 백엔드 파일 분석 결과 (정규화) */
export interface AudioAnalysisResult {
  logId: number;
  segments: AudioSegment[];
  isPhishing: boolean;
  riskScore: number;
  riskLevel: BackendRiskLevel;
  phishingType: string;
  matchedPatterns: string[];
  coreEvidence: string;
}

export const ANALYZE_AUDIO_URL = `${BASE_URL_HTTP}${ANALYZE_AUDIO_PATH}`;

export function guessMime(fileName: string): string {
  const ext = fileName.toLowerCase().split('.').pop();
  switch (ext) {
    case 'mp3':
      return 'audio/mpeg';
    case 'm4a':
      return 'audio/mp4';
    case 'aac':
      return 'audio/aac';
    case 'ogg':
      return 'audio/ogg';
    case 'flac':
      return 'audio/flac';
    case 'wav':
    default:
      return 'audio/wav';
  }
}

/** fetch 응답을 검사하고 정규화된 분석 결과로 변환한다. */
export async function parseAnalyzeResponse(res: Response): Promise<AudioAnalysisResult> {
  const raw = await res.text().catch(() => '');
  // 디버깅: 백엔드 원본 응답을 콘솔에 남긴다(웹 F12 Console에서 확인).
  // eslint-disable-next-line no-console
  console.log('[VoiceGuard] analyze-audio 응답', res.status, raw.slice(0, 3000));

  if (!res.ok) {
    let detail = raw;
    try {
      detail = (JSON.parse(raw) as { detail?: string })?.detail ?? raw;
    } catch {
      /* raw 유지 */
    }
    throw new Error(`분석 실패 (${res.status}) ${detail}`.trim());
  }

  let data: {
    log_id?: number;
    segments?: { start_time?: number; end_time?: number; speaker?: unknown; text?: string }[];
    is_phishing?: boolean;
    risk_score?: number;
    risk_level?: BackendRiskLevel;
    phishing_type?: string;
    matched_patterns?: string[];
    core_evidence?: string;
  };
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error('서버 응답을 JSON으로 해석할 수 없습니다: ' + raw.slice(0, 200));
  }

  const segments: AudioSegment[] = (data.segments ?? [])
    .map((s) => ({
      speaker: s.speaker != null ? String(s.speaker) : 'unknown',
      text: (s.text ?? '').trim(),
      start: s.start_time ?? 0,
      end: s.end_time ?? 0,
    }))
    .filter((s) => s.text.length > 0);

  return {
    logId: data.log_id ?? 0,
    segments,
    isPhishing: Boolean(data.is_phishing),
    riskScore: data.risk_score ?? 0,
    riskLevel: data.risk_level ?? 'low',
    phishingType: data.phishing_type ?? '',
    matchedPatterns: data.matched_patterns ?? [],
    coreEvidence: data.core_evidence ?? '',
  };
}
