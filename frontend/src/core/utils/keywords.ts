/**
 * 위험 키워드 사전 + 통화 유형 분류 (프론트 근사).
 *
 * 백엔드는 카테고리(matched_patterns)와 근거 문장 1개(core_evidence)만 제공하고
 * 개별 단어 위치는 주지 않는다(05_BACKEND_REQUESTS 항목 4). 따라서 말풍선/근거의
 * 단어 하이라이트와 통화 "유형" 라벨은 앱이 이 사전으로 근사 매칭한다.
 *
 * 카테고리 정의는 백엔드 rag_detector.RuleSignalDetector.PATTERNS 와 정렬.
 */

/** 카테고리 → 하이라이트용 리터럴 키워드 목록 */
export const KEYWORD_DICT: Record<string, string[]> = {
  '수사기관/공공기관 사칭': ['검찰', '경찰', '금융감독원', '금감원', '법원', '수사관', '검사님'],
  '범죄 연루 압박': ['범죄', '연루', '대포통장', '명의도용', '명의 도용', '구속', '체포', '영장'],
  '금전 이체 유도': ['안전계좌', '안전 계좌', '이체', '송금', '입금', '현금 인출', '강제상환', '강제 상환'],
  '개인정보/인증 요구': ['주민등록번호', '계좌번호', '비밀번호', '인증번호', 'OTP'],
  '앱 설치/원격제어 유도': ['앱 설치', '원격제어', '원격', 'URL', '링크'],
  '긴급성/비밀 유지 압박': ['지금 바로', '즉시', '오늘 안', '비밀', '말하지'],
  // 대출빙자형 보조 키워드(디자인 화면 5·8에 등장)
  '대출/신용 빙자': ['저금리', '대출', '신용평점', '신용 평점', '신용등급', '신용 등급', '연장', '우회'],
};

/** 모든 키워드를 평평하게 (긴 단어 우선 정렬 → 하이라이트 겹침 방지) */
export const ALL_KEYWORDS: string[] = Array.from(
  new Set(Object.values(KEYWORD_DICT).flat()),
).sort((a, b) => b.length - a.length);

/** 텍스트에서 등장한 위험 키워드 추출(중복 제거, 최대 n개) */
export function extractKeywords(text: string, max = 8): string[] {
  const found: string[] = [];
  for (const kw of ALL_KEYWORDS) {
    if (text.includes(kw) && !found.some((f) => f.includes(kw) || kw.includes(f))) {
      found.push(kw);
    }
    if (found.length >= max) break;
  }
  return found;
}

/**
 * matched_patterns + 통화 텍스트로 "유형" 라벨을 근사 추정.
 * 히스토리/결과 화면의 유형 표기에 사용.
 */
export function categorizeType(matchedPatterns: string[], text: string): string {
  const has = (kw: string) => text.includes(kw);
  const hasPattern = (p: string) => matchedPatterns.includes(p);

  if (has('저금리') || has('신용평점') || has('신용 평점') || has('대출') || has('강제상환')) {
    return '대출사기형';
  }
  if (
    hasPattern('수사기관/공공기관 사칭') ||
    hasPattern('범죄 연루 압박') ||
    has('검찰') ||
    has('금감원')
  ) {
    return '수사기관 사칭형';
  }
  if (has('납치') || has('협박') || has('사고') || has('가족')) {
    return '납치·협박형';
  }
  if (matchedPatterns.length > 0) return '의심 통화';
  return '정상 통화';
}
