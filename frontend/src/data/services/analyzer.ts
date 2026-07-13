import type { BackendRiskLevel } from '@/data/models/types';

/**
 * 앱 내부 목(mock) 분석기.
 *
 * 백엔드 app/services/rag_detector.py 의 RuleSignalDetector 규칙 신호를 옮겨와,
 * 백엔드 없이도(USE_MOCK_WS=true) 현실적인 위험도/근거를 만들어 낸다.
 * RAG 유사도 부분은 코퍼스가 없어 카테고리별 가중치 합으로 근사한다.
 * (실제 백엔드 연결 시에는 이 파일이 아니라 서버 결과를 사용)
 */

const PATTERNS: Record<string, { regex: RegExp[]; weight: number; evidence: string }> = {
  '수사기관/공공기관 사칭': {
    regex: [/검찰/, /경찰/, /금융감독원/, /금감원/, /법원/, /수사관/],
    weight: 0.42,
    evidence: '검찰·금감원 등 수사기관/공공기관을 사칭하는 표현이 탐지되었습니다.',
  },
  '범죄 연루 압박': {
    regex: [/범죄.*연루/, /대포통장/, /명의.*도용/, /구속/, /체포/, /영장/],
    weight: 0.28,
    evidence: '계좌가 범죄에 연루되었다며 압박하는 정황이 확인되었습니다.',
  },
  '금전 이체 유도': {
    regex: [/안전계좌/, /이체/, /송금/, /입금/, /현금.*인출/, /강제.?상환/],
    weight: 0.26,
    evidence: '안전계좌 이체 등 금전을 요구·유도하는 표현이 탐지되었습니다.',
  },
  '개인정보/인증 요구': {
    regex: [/주민등록번호/, /계좌번호/, /비밀번호/, /인증번호/, /OTP/i],
    weight: 0.22,
    evidence: '계좌번호·인증번호 등 민감한 개인정보를 요구하고 있습니다.',
  },
  '앱 설치/원격제어 유도': {
    regex: [/앱.*설치/, /원격/, /원격제어/, /URL/i, /링크.*클릭/],
    weight: 0.18,
    evidence: '앱 설치·원격제어를 유도하는 표현이 탐지되었습니다.',
  },
  '긴급성/비밀 유지 압박': {
    regex: [/지금.*바로/, /즉시/, /오늘.*안/, /비밀/, /말하지.*마/],
    weight: 0.14,
    evidence: '즉시 처리·비밀 유지를 강요하는 압박 정황이 있습니다.',
  },
  '대출/신용 빙자': {
    regex: [/저금리/, /신용.?평점/, /신용.?등급/, /대출/, /연장/, /우회/],
    weight: 0.4,
    evidence: '저금리 대출·신용평점 하락을 빙자해 상환/이체를 압박하고 있습니다.',
  },
};

export interface AnalyzeResult {
  isPhishing: boolean;
  riskScore: number; // 0..1
  riskLevel: BackendRiskLevel;
  matchedPatterns: string[];
  coreEvidence: string;
}

function backendRiskLevel(score: number): BackendRiskLevel {
  if (score >= 0.75) return 'high';
  if (score >= 0.45) return 'medium';
  return 'low';
}

/** 누적 통화 텍스트를 분석 */
export function analyze(text: string): AnalyzeResult {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  const matched: string[] = [];
  let score = 0;

  for (const [name, def] of Object.entries(PATTERNS)) {
    if (def.regex.some((r) => r.test(cleaned))) {
      matched.push(name);
      score += def.weight;
    }
  }
  score = Math.min(score, 0.96);

  const primary = matched[0];
  const coreEvidence = primary
    ? PATTERNS[primary].evidence
    : '특별한 위험 신호가 발견되지 않았습니다.';

  return {
    isPhishing: score >= 0.6,
    riskScore: Math.round(score * 10000) / 10000,
    riskLevel: backendRiskLevel(score),
    matchedPatterns: matched,
    coreEvidence,
  };
}
