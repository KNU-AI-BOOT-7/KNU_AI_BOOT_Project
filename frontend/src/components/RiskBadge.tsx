import { View } from 'react-native';
import { AppText } from './AppText';
import { Icon } from './Icon';
import { useTheme } from '@/core/theme/theme';
import {
  riskColor,
  riskColorFaint,
  riskColorText,
  riskIcon,
  riskLabel,
  type RiskLevel,
} from '@/core/utils/riskLevel';

/**
 * 위험 등급 배지 — 색 + 아이콘 + 텍스트를 항상 함께(접근성 필수).
 * variant: 'soft'(연한 배경 pill) | 'solid'(꽉찬 색)
 */
export function RiskBadge({
  level,
  variant = 'soft',
  size = 'md',
}: {
  level: RiskLevel;
  variant?: 'soft' | 'solid';
  size?: 'sm' | 'md';
}) {
  const { colors } = useTheme();
  const main = riskColor(level, colors);
  const label = riskLabel(level);
  const fontSize = size === 'sm' ? 11.5 : 13;
  const iconSize = size === 'sm' ? 13 : 15;

  const bg = variant === 'solid' ? main : riskColorFaint(level, colors);
  const fg = variant === 'solid' ? '#FFFFFF' : riskColorText(level, colors);

  return (
    <View
      accessibilityLabel={`위험 등급 ${label}`}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 5,
        backgroundColor: bg,
        paddingHorizontal: size === 'sm' ? 8 : 10,
        paddingVertical: size === 'sm' ? 4 : 5,
        borderRadius: 20,
        alignSelf: 'flex-start',
      }}
    >
      <Icon name={riskIcon(level)} size={iconSize} color={fg} />
      <AppText weight="700" color={fg} style={{ fontSize }}>
        {label}
      </AppText>
    </View>
  );
}
