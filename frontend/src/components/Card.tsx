import { View, type ViewProps, type ViewStyle } from 'react-native';
import { useTheme } from '@/core/theme/theme';

/** 흰 카드 컨테이너 (라운드 + 그림자). 좌측 색 스트라이프 옵션. */
export function Card({
  children,
  style,
  stripeColor,
  padding = 16,
  ...rest
}: ViewProps & { style?: ViewStyle; stripeColor?: string; padding?: number }) {
  const { colors } = useTheme();
  return (
    <View
      {...rest}
      style={[
        {
          backgroundColor: colors.card,
          borderRadius: 16,
          padding,
          overflow: 'hidden',
          shadowColor: '#1E2838',
          shadowOpacity: 0.06,
          shadowRadius: 12,
          shadowOffset: { width: 0, height: 4 },
          elevation: 2,
        },
        stripeColor
          ? { borderLeftWidth: 5, borderLeftColor: stripeColor }
          : null,
        style,
      ]}
    >
      {children}
    </View>
  );
}
