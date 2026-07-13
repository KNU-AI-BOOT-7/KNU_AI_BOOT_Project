import { View } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '@/core/theme/theme';

/** 탐지 키워드 칩 */
export function KeywordChip({ text }: { text: string }) {
  const { colors, isDark } = useTheme();
  return (
    <View
      style={{
        backgroundColor: isDark ? colors.primaryFaint : '#E4ECFB',
        paddingHorizontal: 16,
        paddingVertical: 9,
        borderRadius: 22,
      }}
    >
      <AppText weight="600" color={colors.primary} style={{ fontSize: 14 }}>
        {text}
      </AppText>
    </View>
  );
}
