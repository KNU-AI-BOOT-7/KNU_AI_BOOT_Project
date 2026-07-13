import type { ThemeColors } from '@/core/theme/colors';

/**
 * 위험 등급 — UI 진실 소스(단일 소스).
 *
 * 문서 3중 불일치(API low/med/high, 기능명세서 70/85, Figma 84%)를 여기서 통일.
 * → 기능명세서 §10 기준(주의 70% / 강한경고 85%)을 채택하고 risk_score에서 직접 계산.
 * 강한경고(danger) 임계값은 설정 슬라이더로 0.70~0.85 조정 가능.
 */
export type RiskLevel = 'safe' | 'warning' | 'danger';

export const WARNING_THRESHOLD = 0.7; // 주의
export const DEFAULT_DANGER_THRESHOLD = 0.85; // 강한 경고(전면 모달 트리거)

export function riskLevelFromScore(
  score: number,
  dangerThreshold: number = DEFAULT_DANGER_THRESHOLD,
): RiskLevel {
  if (score >= dangerThreshold) return 'danger';
  if (score >= WARNING_THRESHOLD) return 'warning';
  return 'safe';
}

/** 0~1 점수를 정수 % 로 */
export function toPercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100);
}

export function riskLabel(level: RiskLevel): string {
  switch (level) {
    case 'danger':
      return '위험';
    case 'warning':
      return '주의';
    default:
      return '정상';
  }
}

/** 경고 화면 헤더용 강조 라벨 */
export function riskHeadline(level: RiskLevel): string {
  switch (level) {
    case 'danger':
      return '강한 경고';
    case 'warning':
      return '주의 필요';
    default:
      return '정상';
  }
}

export function riskColor(level: RiskLevel, colors: ThemeColors): string {
  switch (level) {
    case 'danger':
      return colors.danger;
    case 'warning':
      return colors.warning;
    default:
      return colors.safe;
  }
}

export function riskColorText(level: RiskLevel, colors: ThemeColors): string {
  switch (level) {
    case 'danger':
      return colors.dangerText;
    case 'warning':
      return colors.warningText;
    default:
      return colors.safeText;
  }
}

export function riskColorFaint(level: RiskLevel, colors: ThemeColors): string {
  switch (level) {
    case 'danger':
      return colors.dangerFaint;
    case 'warning':
      return colors.warningFaint;
    default:
      return colors.safeFaint;
  }
}

/** Icon 컴포넌트에서 쓰는 아이콘 이름 */
export function riskIcon(level: RiskLevel): 'shield-check' | 'alert-triangle' | 'alert-octagon' {
  switch (level) {
    case 'danger':
      return 'alert-octagon';
    case 'warning':
      return 'alert-triangle';
    default:
      return 'shield-check';
  }
}
