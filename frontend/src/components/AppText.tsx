import { Text, type TextProps, type TextStyle, StyleSheet } from 'react-native';
import { useTheme } from '@/core/theme/theme';

type Weight = '400' | '500' | '600' | '700' | '800';

/**
 * 앱 공통 텍스트.
 * - 큰 글씨 모드(설정) 배율을 fontSize에 자동 적용.
 * - weight로 굵기 지정, 기본 색은 테마 본문색.
 */
export function AppText({
  weight = '400',
  color,
  style,
  children,
  ...rest
}: TextProps & { weight?: Weight; color?: string }) {
  const { colors, fontScale } = useTheme();
  const flat = (StyleSheet.flatten(style) ?? {}) as TextStyle;
  const baseSize = typeof flat.fontSize === 'number' ? flat.fontSize : 14;

  return (
    <Text
      {...rest}
      style={[
        { color: color ?? colors.text, fontWeight: weight },
        style,
        { fontSize: baseSize * fontScale },
      ]}
    >
      {children}
    </Text>
  );
}
