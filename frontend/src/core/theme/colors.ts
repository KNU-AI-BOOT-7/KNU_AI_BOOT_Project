/**
 * 색상 팔레트 — 디자인 HTML(최종 앱 디자인.html)의 실제 색을 단일 소스로 정리.
 * 위험 정보는 항상 "색 + 아이콘 + 텍스트"로 함께 전달한다(고령/색약 접근성).
 */

export type ThemeColors = {
  // 브랜드
  primary: string;
  primaryDark: string;
  primaryFaint: string; // 아이콘 배경/정보 박스 틴트
  onPrimary: string;

  // 위험 등급 (정상/주의/위험)
  safe: string;
  safeText: string;
  safeFaint: string;
  warning: string;
  warningText: string;
  warningFaint: string;
  danger: string;
  dangerText: string;
  dangerFaint: string;

  // 표면
  bg: string; // 화면 배경
  card: string; // 카드
  cardAlt: string; // 보조 카드/입력 배경
  border: string;

  // 텍스트
  text: string;
  textSecondary: string;
  textMuted: string;

  // 부가
  accentViolet: string;
  accentVioletFaint: string;
  shadow: string;
};

/** 밝은 테마 */
export const lightColors: ThemeColors = {
  primary: '#2563EB',
  primaryDark: '#1D4ED8',
  primaryFaint: '#E7EEFE',
  onPrimary: '#FFFFFF',

  safe: '#1F9D57',
  safeText: '#1F9D57',
  safeFaint: '#DFF3E6',
  warning: '#F5A623',
  warningText: '#E0A11B',
  warningFaint: '#FBF1D6',
  danger: '#E11D2A',
  dangerText: '#E11D2A',
  dangerFaint: '#FCE4E6',

  bg: '#F4F6F9',
  card: '#FFFFFF',
  cardAlt: '#F1F3F6',
  border: '#EDEFF2',

  text: '#1F2937',
  textSecondary: '#7B8494',
  textMuted: '#9AA2AE',

  accentViolet: '#6D5BD0',
  accentVioletFaint: '#EAE7FB',
  shadow: 'rgba(30,40,60,0.10)',
};

/** 다크 테마 (One UI 다크 대응) */
export const darkColors: ThemeColors = {
  primary: '#3B82F6',
  primaryDark: '#2563EB',
  primaryFaint: '#1E2A44',
  onPrimary: '#FFFFFF',

  safe: '#34C77B',
  safeText: '#4ADE80',
  safeFaint: '#16301F',
  warning: '#F5A623',
  warningText: '#F5B942',
  warningFaint: '#2E2716',
  danger: '#F5544A',
  dangerText: '#FB7169',
  dangerFaint: '#3A1D1D',

  bg: '#121212',
  card: '#1C2530',
  cardAlt: '#242E3B',
  border: '#2A3442',

  text: '#ECEFF3',
  textSecondary: '#9AA5B3',
  textMuted: '#7B8798',

  accentViolet: '#9C8CF0',
  accentVioletFaint: '#241F3A',
  shadow: 'rgba(0,0,0,0.5)',
};

/**
 * 통화 화면(4·5)은 디자인상 항상 어두운 통화 UI, 경고(6)는 항상 빨강.
 * 테마와 무관하게 고정 사용하는 색.
 */
export const fixedColors = {
  callBg: '#1B232F',
  callBgChat: '#141B24',
  callCard: '#242E3B',
  callBubbleOther: '#2A3442',
  callText: '#FFFFFF',
  callTextDim: '#8A96A6',
  callTextSub: '#7B8798',
  hangup: '#E4362E',
  warningScreen: '#E11D2A',
  amber: '#F5A623',
  rec: '#F5544A',
};
