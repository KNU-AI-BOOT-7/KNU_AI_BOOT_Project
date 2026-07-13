import { ActivityIndicator, Pressable, View, type ViewStyle } from 'react-native';
import { AppText } from './AppText';
import { Icon, type IconName } from './Icon';
import { useTheme } from '@/core/theme/theme';

type Variant = 'filled' | 'outlined' | 'white';

/** Material3 스타일 버튼. 최소 터치 높이 52dp (접근성). */
export function Button({
  title,
  onPress,
  variant = 'filled',
  color,
  textColor,
  icon,
  loading = false,
  disabled = false,
  style,
}: {
  title: string;
  onPress?: () => void;
  variant?: Variant;
  color?: string;
  textColor?: string;
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}) {
  const { colors } = useTheme();
  const primary = color ?? colors.primary;

  let bg = primary;
  let fg = textColor ?? colors.onPrimary;
  let border = 'transparent';
  if (variant === 'outlined') {
    bg = 'transparent';
    fg = textColor ?? primary;
    border = primary;
  } else if (variant === 'white') {
    bg = '#FFFFFF';
    fg = textColor ?? primary;
  }

  return (
    <Pressable
      onPress={disabled || loading ? undefined : onPress}
      android_ripple={{ color: 'rgba(0,0,0,0.08)' }}
      style={({ pressed }) => [
        {
          minHeight: 52,
          borderRadius: 15,
          backgroundColor: bg,
          borderWidth: variant === 'outlined' ? 1.5 : 0,
          borderColor: border,
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: 9,
          paddingHorizontal: 20,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        },
        style,
      ]}
      accessibilityRole="button"
      accessibilityLabel={title}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon ? <Icon name={icon} size={20} color={fg} /> : null}
          <AppText weight="700" color={fg} style={{ fontSize: 16 }}>
            {title}
          </AppText>
        </>
      )}
    </Pressable>
  );
}
