import { useColorScheme } from 'react-native';
import { useSettingsStore } from '@/state/settingsStore';
import { darkColors, lightColors, type ThemeColors } from './colors';

export type Theme = {
  colors: ThemeColors;
  isDark: boolean;
  /** 큰 글씨 모드 배율 (1.0 또는 1.2) */
  fontScale: number;
};

/**
 * 현재 테마를 반환. 설정(themeMode)이 'system'이면 OS 설정을 따른다.
 * 큰 글씨 모드는 fontScale로 노출하고, sp() 헬퍼로 폰트에 적용한다.
 */
export function useTheme(): Theme {
  const system = useColorScheme();
  const themeMode = useSettingsStore((s) => s.themeMode);
  const largeText = useSettingsStore((s) => s.largeText);

  const isDark = themeMode === 'system' ? system === 'dark' : themeMode === 'dark';

  return {
    colors: isDark ? darkColors : lightColors,
    isDark,
    fontScale: largeText ? 1.2 : 1.0,
  };
}
