/**
 * 정적 안내 콘텐츠 (정보/예방/경고 화면 공유).
 *
 * 권장 행동(recommended_action)은 WS 응답에 없어(05 항목 11) 유형별로 앱에 정적 매핑.
 */

export const URGENT_STEPS: string[] = [
  '개인정보·계좌·인증번호는 절대 알려주지 마세요',
  '즉시 전화를 끊고 해당 기관에 직접 재확인하세요',
  '이미 송금했다면 은행에 지급정지를 즉시 요청하세요',
];

export interface ResponseType {
  title: string;
  body: string;
}

export const TYPE_RESPONSES: ResponseType[] = [
  {
    title: '기관 사칭형',
    body: '검찰·경찰·금감원은 절대 전화로 금전 이체나 계좌 확인을 요구하지 않습니다. 발신번호를 조작한 것이니 안내받은 번호로 재발신하지 마세요.',
  },
  {
    title: '대출 빙자형',
    body: '"신용점수 하락", "즉시 상환"으로 압박해도 정식 금융사는 강제 이체를 요구하지 않습니다. 대출 관련 연락은 등록된 대표번호로 직접 확인하세요.',
  },
  {
    title: '납치·협박형',
    body: '가족을 빙자해 송금을 강요하면, 먼저 전화를 끊고 가족에게 직접 연락해 안전을 확인하세요. 당황하지 말고 112에 신고하세요.',
  },
];

export interface PreventionType {
  title: string;
  desc: string;
  tone: 'danger' | 'warning';
}

export const PREVENTION_TYPES: PreventionType[] = [
  { title: '수사기관 사칭형', desc: '검찰·경찰 사칭, 안전계좌 이체 요구', tone: 'danger' },
  { title: '대출사기형', desc: '저금리 미끼, 수수료·보증금 선입금 유도', tone: 'warning' },
  { title: '납치·협박형', desc: '가족 위험으로 심리 압박, 즉시 송금 강요', tone: 'danger' },
];

export const THREE_SECOND_RULE =
  '끊는다 → 공식 번호로 확인한다 → 계좌·인증번호는 절대 말하지 않는다';

export const FSS_REPORT_NUMBER = '1332';

/** matched_patterns 카테고리 → 경고/근거 화면용 짧은 문구 */
const PATTERN_BULLET: Record<string, string> = {
  '수사기관/공공기관 사칭': '수사기관 사칭 표현',
  '범죄 연루 압박': '계좌 범죄 연루 언급',
  '금전 이체 유도': '금전 이체 유도 정황',
  '개인정보/인증 요구': '개인정보·인증번호 요구',
  '앱 설치/원격제어 유도': '앱 설치·원격제어 유도',
  '긴급성/비밀 유지 압박': '긴급성·비밀 유지 압박',
  '대출/신용 빙자': '저금리 대출·신용 빙자',
};

export function evidenceBullets(matchedPatterns: string[]): string[] {
  const bullets = matchedPatterns.map((p) => PATTERN_BULLET[p] ?? p);
  return bullets.length ? bullets : ['보이스피싱 의심 표현'];
}

/** 유형별 권장 행동 문구 (경고/결과 화면) */
export function recommendedAction(category: string): string {
  if (category.includes('대출')) {
    return '통화를 종료하고, 대출 관련 연락은 금융사 공식 대표번호로 직접 확인하세요.';
  }
  if (category.includes('납치') || category.includes('협박')) {
    return '전화를 끊고 가족에게 직접 연락해 안전을 확인한 뒤, 112에 신고하세요.';
  }
  if (category.includes('수사기관') || category.includes('사칭')) {
    return '즉시 통화를 종료하고, 해당 기관의 공식 대표번호로 직접 확인하세요.';
  }
  return '통화를 종료하고 공식 대표번호로 직접 확인하세요.';
}
