/**
 * 스크립트 통화 시나리오 (목 STT 재생용).
 *
 * Expo Go에서는 온디바이스 STT를 쓸 수 없으므로, 미리 준비한 발화를 시간축에 맞춰
 * 재생해 실시간 인식을 흉내낸다(03_SCREENS 화면3 폴백 (b) 경로와 동일 개념).
 * 각 turn을 WS로 흘려보내면 실제 파이프라인(화면 4~7)이 그대로 동작한다.
 */

export interface ScenarioTurn {
  atSec: number; // 통화 시작 기준 등장 시각(초)
  isMine: boolean; // true=나(우측 파랑), false=상대방(좌측 회색)
  role: string; // 백엔드 role
  content: string;
}

export interface Scenario {
  id: string;
  title: string; // 예상 유형(데모 표기)
  phone: string;
  source: 'realtime' | 'file';
  turns: ScenarioTurn[];
}

const SPK_OTHER = 'speaker_a';
const SPK_ME = 'speaker_b';

/** 검찰 사칭형 — safe → 주의 → 위험 으로 상승(경고 모달 트리거) */
export const scenarioProsecutor: Scenario = {
  id: 'prosecutor',
  title: '수사기관 사칭형',
  phone: '010-7412-5290',
  source: 'realtime',
  turns: [
    { atSec: 2, isMine: false, role: SPK_OTHER, content: '안녕하세요, 서울중앙지검 첨단범죄수사부 김민수 수사관입니다.' },
    { atSec: 8, isMine: true, role: SPK_ME, content: '네? 무슨 일이시죠?' },
    { atSec: 14, isMine: false, role: SPK_OTHER, content: '고객님 명의 계좌가 대포통장으로 범죄에 연루되어 구속 영장이 청구된 상황입니다.' },
    { atSec: 22, isMine: true, role: SPK_ME, content: '제가요? 그런 적 없는데요...' },
    { atSec: 28, isMine: false, role: SPK_OTHER, content: '지금 즉시 확인하지 않으면 체포됩니다. 이건 비밀 수사라 아무에게도 말하지 마세요.' },
    { atSec: 37, isMine: true, role: SPK_ME, content: '어떻게 해야 하나요?' },
    { atSec: 43, isMine: false, role: SPK_OTHER, content: '안전계좌로 지금 바로 전액을 이체하시면 조사가 중단됩니다. 계좌번호를 불러드릴게요.' },
  ],
};

/** 대출 빙자형 — 주의 수준까지 상승 */
export const scenarioLoan: Scenario = {
  id: 'loan',
  title: '대출사기형',
  phone: '010-3928-1174',
  source: 'realtime',
  turns: [
    { atSec: 2, isMine: false, role: SPK_OTHER, content: '고객님, 저희 쪽에서 확인해보니 신용 등급이 낮아서 지금 대출 연장이 어려운 상황이세요.' },
    { atSec: 10, isMine: true, role: SPK_ME, content: '네? 무슨 말씀이신지 잘 모르겠는데요, 어디시라고요?' },
    { atSec: 17, isMine: false, role: SPK_OTHER, content: '저희는 저금리 대출 전문 상담팀이고요, 지금 신용평점 조회 결과가 안 좋게 나와서 연락드린 거예요.' },
    { atSec: 26, isMine: true, role: SPK_ME, content: '저는 신청한 적 없는데, 어느 회사시죠?' },
    { atSec: 33, isMine: false, role: SPK_OTHER, content: '신용평점이 계속 내려가고 있어서, 강제상환 처리 전에 즉시 우회 입금하셔야 해요.' },
  ],
};

/** 정상 통화 — 위험 신호 없음 */
export const scenarioNormal: Scenario = {
  id: 'normal',
  title: '정상 통화',
  phone: '1588-1234',
  source: 'file',
  turns: [
    { atSec: 2, isMine: false, role: SPK_OTHER, content: '안녕하세요, OO카드 고객센터입니다. 이번 달 결제 예정 금액 안내차 연락드렸어요.' },
    { atSec: 9, isMine: true, role: SPK_ME, content: '네, 결제일이 언제죠?' },
    { atSec: 15, isMine: false, role: SPK_OTHER, content: '이번 달 25일에 자동이체 예정이고, 금액은 32만 원입니다.' },
  ],
};

export const SCENARIOS: Scenario[] = [scenarioProsecutor, scenarioLoan, scenarioNormal];

export function getScenario(id?: string | null): Scenario {
  return SCENARIOS.find((s) => s.id === id) ?? scenarioProsecutor;
}
