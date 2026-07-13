import { View } from 'react-native';
import { Icon, type IconName } from './Icon';

/** 색 배경의 둥근 아이콘 컨테이너 (카드 좌측 아이콘 등에 반복 사용) */
export function IconCircle({
  name,
  color,
  bg,
  size = 44,
  radius,
  iconSize,
}: {
  name: IconName;
  color: string;
  bg: string;
  size?: number;
  radius?: number;
  iconSize?: number;
}) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: radius ?? size * 0.28,
        backgroundColor: bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Icon name={name} size={iconSize ?? size * 0.5} color={color} />
    </View>
  );
}
