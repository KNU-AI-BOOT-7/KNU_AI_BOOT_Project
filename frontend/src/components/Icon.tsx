import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';

/** 앱에서 쓰는 아이콘 이름 → 벡터 아이콘 매핑 (단일 진입점) */
export type IconName =
  | 'shield'
  | 'shield-check'
  | 'shield-alert'
  | 'mic'
  | 'bell'
  | 'lock'
  | 'settings'
  | 'home'
  | 'clock'
  | 'info'
  | 'activity'
  | 'upload'
  | 'chevron-right'
  | 'chevron-left'
  | 'share'
  | 'file'
  | 'alert-triangle'
  | 'alert-octagon'
  | 'check-circle'
  | 'x'
  | 'x-circle'
  | 'phone'
  | 'phone-off'
  | 'phone-forwarded'
  | 'volume'
  | 'volume-x'
  | 'user'
  | 'more'
  | 'grid'
  | 'video'
  | 'record'
  | 'bluetooth'
  | 'trash';

type Family = 'feather' | 'mci';
const MAP: Record<IconName, [Family, string]> = {
  shield: ['mci', 'shield-outline'],
  'shield-check': ['mci', 'shield-check'],
  'shield-alert': ['mci', 'shield-alert'],
  mic: ['feather', 'mic'],
  bell: ['feather', 'bell'],
  lock: ['feather', 'lock'],
  settings: ['feather', 'settings'],
  home: ['feather', 'home'],
  clock: ['feather', 'clock'],
  info: ['feather', 'info'],
  activity: ['feather', 'activity'],
  upload: ['feather', 'upload-cloud'],
  'chevron-right': ['feather', 'chevron-right'],
  'chevron-left': ['feather', 'chevron-left'],
  share: ['feather', 'share-2'],
  file: ['feather', 'file-text'],
  'alert-triangle': ['feather', 'alert-triangle'],
  'alert-octagon': ['feather', 'alert-octagon'],
  'check-circle': ['feather', 'check-circle'],
  x: ['feather', 'x'],
  'x-circle': ['feather', 'x-circle'],
  phone: ['feather', 'phone'],
  'phone-off': ['feather', 'phone-off'],
  'phone-forwarded': ['feather', 'phone-forwarded'],
  volume: ['feather', 'volume-2'],
  'volume-x': ['feather', 'volume-x'],
  user: ['feather', 'user'],
  more: ['feather', 'more-vertical'],
  grid: ['feather', 'grid'],
  video: ['feather', 'video'],
  record: ['mci', 'record-circle-outline'],
  bluetooth: ['mci', 'bluetooth'],
  trash: ['feather', 'trash-2'],
};

export function Icon({
  name,
  size = 22,
  color = '#1F2937',
}: {
  name: IconName;
  size?: number;
  color?: string;
}) {
  const [family, iconName] = MAP[name];
  if (family === 'mci') {
    return <MaterialCommunityIcons name={iconName as never} size={size} color={color} />;
  }
  return <Feather name={iconName as never} size={size} color={color} />;
}
