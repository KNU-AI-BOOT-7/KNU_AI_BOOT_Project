import { View } from 'react-native';
import { AppText } from './AppText';
import { Icon, type IconName } from './Icon';
import { useTheme } from '@/core/theme/theme';

/** 파란 안내/정보 노트 박스 */
export function InfoBanner({
  text,
  icon = 'info',
}: {
  text: string;
  icon?: IconName;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        gap: 9,
        alignItems: 'flex-start',
        backgroundColor: colors.primaryFaint,
        borderRadius: 12,
        padding: 13,
      }}
    >
      <View style={{ marginTop: 1 }}>
        <Icon name={icon} size={16} color={colors.primary} />
      </View>
      <AppText color={colors.primary} style={{ fontSize: 12.5, lineHeight: 18, flex: 1 }}>
        {text}
      </AppText>
    </View>
  );
}
