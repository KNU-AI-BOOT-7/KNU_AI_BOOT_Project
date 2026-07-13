/**
 * 앱 환경 설정 (한 곳에서 관리).
 *
 * - 실제 백엔드와 붙일 때는 USE_MOCK_WS를 false로 바꾸고 BASE_URL_WS를
 *   데모용 ngrok/cloudflared 주소(wss://...)로 교체한다.
 * - 기본값은 "완전 목데이터" 모드: 백엔드 없이 앱만으로 동작한다(Expo Go 데모).
 */

/**
 * true면 백엔드 없이 앱 내부 목 분석기로 동작(Expo Go 데모용).
 * false(실사용): 실제 WebSocket으로 백엔드 연결. BASE_URL_WS를 실제 서버 주소로 맞출 것.
 */
export const USE_MOCK_WS = false;

/**
 * true면 항상 스크립트 시나리오 재생(강제 목).
 * false(기본)면 "가능하면 실제 온디바이스 STT" — 단, Expo Go에서는 네이티브 모듈이 없어
 * 자동으로 목으로 폴백한다(executionEnvironment로 감지). 실제 STT는 dev build에서 동작.
 */
export const USE_MOCK_STT = false;

/**
 * 백엔드 주소 (파일 전사 STT + 채점 전담).
 *
 * 파일(녹음) 분석: 프론트는 캡처한 오디오 원본을 그대로 백엔드로 업로드하고,
 * 백엔드가 Whisper로 전사(화자분리 없음) 후 KoELECTRA/RAG로 채점한다.
 * 프론트에서 STT/변환을 하지 않으므로 재인코딩이 없다.
 * 실시간 분석은 별도: 웹=Web Speech API, 앱=온디바이스 STT(WS로 텍스트 전송).
 *
 * .env(EXPO_PUBLIC_API_BASE)로 주소를 덮어쓸 수 있다. 실기기(Expo Go) 테스트 시
 * 127.0.0.1 대신 PC의 LAN IP(예: http://192.168.0.10:8000)를 넣어야 한다.
 */
const API_BASE = (process.env.EXPO_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

/** 실제 백엔드 HTTP 주소 */
export const BASE_URL_HTTP = API_BASE;
/** 실제 백엔드 WS 주소 (http→ws, https→wss 자동 변환) */
export const BASE_URL_WS = API_BASE.replace(/^http/, 'ws');

/** 파일(녹음) 업로드 → 백엔드 전사+채점 엔드포인트 경로 */
export const ANALYZE_AUDIO_PATH = '/calls/analyze-audio';

/** 실시간 분석 WS 엔드포인트 경로 */
export const WS_ANALYZE_PATH = '/ws/calls/analyze';

/** start 메시지에 쓸 고정 device_id (백엔드 발급 규칙 미정 → MVP 고정값) */
export const DEVICE_ID = 1;
