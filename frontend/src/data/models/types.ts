/**
 * 데이터 모델.
 * REST/WS 응답은 실제 백엔드(app/schemas.py, main.py) 스키마와 정렬.
 * 앱 내부 모델(TranscriptTurn/CallResult)은 세션 중 앱이 누적하는 요약용.
 */

export type BackendRiskLevel = 'low' | 'medium' | 'high';

/** GET /calls 항목 (백엔드 CallLog) */
export interface CallLog {
  id: number;
  device_id: number | null;
  name: string;
  status: string; // 'normal' | 'phishing'
  risk_score: number; // 0..1
  risk_level: BackendRiskLevel;
  detected_label: number; // 0 | 1
  core_evidence: string;
  created_at: string;
  updated_at: string;
}

/** WS로 저장된 발화 (백엔드 CallMessage) */
export interface CallMessage {
  id: number;
  log_id: number;
  turn_index: number;
  role: string;
  content: string;
  created_at: string;
}

/** 오디오 청크 분석 응답의 전사 1건 (백엔드 audio_analysis_ack.transcripts[]) */
export interface BackendTranscript {
  message_id?: number;
  turn_index?: number;
  role?: string; // 화자분리 없음 → 보통 'unknown'
  content?: string;
  start_time?: number; // 초
  end_time?: number; // 초
}

/** WS 이벤트 (서버 → 클라이언트) — 판별 유니온 */
export type AnalysisEvent =
  | { type: 'call_started'; call: CallLog }
  | {
      type: 'analysis_ack';
      log_id: number;
      is_phishing: false;
      risk_score: number;
      risk_level: BackendRiskLevel;
      message?: CallMessage;
    }
  | {
      type: 'phishing_detected';
      log_id: number;
      is_phishing: true;
      risk_score: number;
      risk_level: BackendRiskLevel;
      matched_patterns: string[];
      core_evidence: string;
      notification?: unknown;
      message?: CallMessage;
    }
  // ── 오디오 청크(실시간 스트리밍) 응답 ── (전사는 백엔드 Whisper가 수행)
  | {
      type: 'audio_analysis_ack';
      log_id: number;
      chunk_index?: number;
      is_phishing: false;
      risk_score: number;
      risk_level: BackendRiskLevel;
      phishing_type?: string;
      transcripts?: BackendTranscript[];
      message_ids?: number[];
    }
  | {
      type: 'audio_phishing_detected';
      log_id: number;
      chunk_index?: number;
      is_phishing: true;
      risk_score: number;
      risk_level: BackendRiskLevel;
      matched_patterns: string[];
      core_evidence: string;
      phishing_type?: string;
      transcripts?: BackendTranscript[];
      notification?: unknown;
      message_ids?: number[];
    }
  | { type: 'audio_chunk_error'; log_id?: number; chunk_index?: number; message: string }
  | { type: 'error'; message: string };

/** 실시간 대화 로그 1턴 (앱이 로컬 기록) */
export interface TranscriptTurn {
  turnIndex: number;
  role: string; // 백엔드 role (예: speaker_a)
  isMine: boolean; // 화면 좌/우 표시용 (온디바이스 화자분리 불가 → 데모 근사)
  content: string;
  atSec: number; // 통화 시작 기준 경과초
  riskScore?: number; // 이 턴 분석 위험도
  keywords?: string[]; // 하이라이트 키워드
}

/** 통화 종료 후 요약 (앱이 세션 동안 누적) */
export interface CallResult {
  id: number;
  name: string;
  category: string;
  finalScore: number; // 최고 위험도 0..1
  matchedPatterns: string[];
  coreEvidence: string;
  keywords: string[];
  turns: TranscriptTurn[];
  source: 'realtime' | 'file';
  createdAt: string; // ISO
  durationSec: number;
}

/** 히스토리/홈 목록 표시용 (CallLog와 CallResult를 통합) */
export interface HistoryItem {
  id: string;
  name: string;
  category: string;
  score: number; // 0..1
  source: 'realtime' | 'file';
  createdAt: string;
  hasDetail: boolean; // 상세(CallResult) 보유 여부
}
