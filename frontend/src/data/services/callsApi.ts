/**
 * 통화 기록(히스토리) 백엔드 조회 API.
 *
 * 히스토리는 로컬이 아니라 백엔드가 진실 소스다.
 *  - 목록/카운트: GET /calls        (API_SPEC 4)
 *  - 상세:        GET /calls/{id}   (API_SPEC 5)
 *
 * 저장은 분석 시점에 이미 백엔드에서 이뤄진다
 * (POST /calls/analyze-audio → log_id 발급, 실시간 WS start → 통화 로그 생성).
 */
import { BASE_URL_HTTP } from '@/core/config/env';
import type { BackendRiskLevel } from '@/data/models/types';

/** GET /calls 목록 항목 */
export interface CallListItem {
  id: number;
  called_at: string; // ISO로 정규화됨
  risk_score: number; // 0..1
  risk_level: BackendRiskLevel;
  phishing_type: string; // 정상 통화면 '정상'
  file_type: string; // 'realtime' | 'recording'
}

/** GET /calls 응답 */
export interface CallsResponse {
  risk_level_counts: { low: number; medium: number; high: number };
  calls: CallListItem[];
}

/** GET /calls/{id} 상세 (얇음: 전사/점수 없음) */
export interface CallDetail {
  id: number;
  phishing_type: string;
  matched_patterns: string[];
  core_evidence: string;
}

/** 백엔드 file_type → 앱 source */
export function callSource(fileType: string | undefined): 'file' | 'realtime' {
  return fileType === 'recording' ? 'file' : 'realtime';
}

/** "2026-07-09 10:20:31" → "2026-07-09T10:20:31" (Date 파싱 안정화) */
function normDate(s: string | undefined): string {
  if (!s) return '';
  return s.includes('T') ? s : s.replace(' ', 'T');
}

export async function fetchCalls(limit = 100): Promise<CallsResponse> {
  const res = await fetch(`${BASE_URL_HTTP}/calls?limit=${limit}`);
  if (!res.ok) throw new Error(`통화 목록 조회 실패 (${res.status})`);
  const data = (await res.json()) as Partial<CallsResponse>;
  const calls = (Array.isArray(data.calls) ? data.calls : []).map((c) => ({
    ...c,
    called_at: normDate(c.called_at),
  })) as CallListItem[];
  return {
    risk_level_counts: data.risk_level_counts ?? { low: 0, medium: 0, high: 0 },
    calls,
  };
}

export async function fetchCallDetail(id: number): Promise<CallDetail> {
  const res = await fetch(`${BASE_URL_HTTP}/calls/${id}`);
  if (!res.ok) throw new Error(`통화 상세 조회 실패 (${res.status})`);
  const data = (await res.json()) as Partial<CallDetail>;
  return {
    id: data.id ?? id,
    phishing_type: data.phishing_type ?? '',
    matched_patterns: Array.isArray(data.matched_patterns) ? data.matched_patterns : [],
    core_evidence: data.core_evidence ?? '',
  };
}
