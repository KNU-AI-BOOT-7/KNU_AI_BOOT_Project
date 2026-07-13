import { Alert, Pressable, ScrollView, Switch, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ScreenHeader } from '@/components/ScreenHeader';
import { useTheme } from '@/core/theme/theme';
import { toPercent } from '@/core/utils/riskLevel';
import { useCallStore } from '@/state/callStore';
import { useSettingsStore, type ThemeMode } from '@/state/settingsStore';

function SectionTitle({ children }: { children: string }) {
  const { colors } = useTheme();
  return (
    <AppText weight="700" color={colors.textSecondary} style={{ fontSize: 13, marginBottom: 8, marginLeft: 4 }}>
      {children}
    </AppText>
  );
}

function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  format,
}: {
  options: T[];
  value: T;
  onChange: (v: T) => void;
  format: (v: T) => string;
}) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <Pressable key={String(opt)} style={{ flex: 1 }} onPress={() => onChange(opt)}>
            <View
              style={{
                paddingVertical: 10,
                borderRadius: 11,
                alignItems: 'center',
                backgroundColor: active ? colors.primary : colors.cardAlt,
              }}
            >
              <AppText weight={active ? '700' : '600'} color={active ? '#FFFFFF' : colors.textSecondary} style={{ fontSize: 13.5 }}>
                {format(opt)}
              </AppText>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function Settings() {
  const { colors } = useTheme();
  const { themeMode, largeText, dangerThreshold, setThemeMode, setLargeText, setDangerThreshold } =
    useSettingsStore();
  const fetchCalls = useCallStore((s) => s.fetchCalls);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <ScreenHeader title="설정" />
        <ScrollView contentContainerStyle={{ padding: 20, gap: 22 }} showsVerticalScrollIndicator={false}>
          <View>
            <SectionTitle>경고 임계값 (강한 경고 트리거)</SectionTitle>
            <Card style={{ gap: 12 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <AppText style={{ fontSize: 14 }}>전면 경고를 띄울 위험도</AppText>
                <AppText weight="800" color={colors.danger} style={{ fontSize: 18 }}>
                  {toPercent(dangerThreshold)}%
                </AppText>
              </View>
              <Segmented
                options={[0.7, 0.75, 0.8, 0.85]}
                value={dangerThreshold}
                onChange={setDangerThreshold}
                format={(v) => `${toPercent(v)}%`}
              />
              <AppText color={colors.textMuted} style={{ fontSize: 12, lineHeight: 17 }}>
                시연 시 조정용. 이 값 이상이면 전면 경고 모달이 자동으로 뜹니다. 주의(노랑) 기준은 70%로 고정입니다.
              </AppText>
            </Card>
          </View>

          <View>
            <SectionTitle>화면</SectionTitle>
            <Card style={{ gap: 16 }}>
              <View style={{ gap: 10 }}>
                <AppText style={{ fontSize: 14 }}>테마</AppText>
                <Segmented<ThemeMode>
                  options={['system', 'light', 'dark']}
                  value={themeMode}
                  onChange={setThemeMode}
                  format={(v) => (v === 'system' ? '시스템' : v === 'light' ? '라이트' : '다크')}
                />
              </View>
              <View style={{ height: 1, backgroundColor: colors.border }} />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <View style={{ flex: 1 }}>
                  <AppText style={{ fontSize: 14 }}>큰 글씨 모드</AppText>
                  <AppText color={colors.textMuted} style={{ fontSize: 12, marginTop: 2 }}>
                    글자 크기를 1.2배로 키웁니다
                  </AppText>
                </View>
                <Switch value={largeText} onValueChange={setLargeText} />
              </View>
            </Card>
          </View>

          <View>
            <SectionTitle>정보</SectionTitle>
            <Card style={{ gap: 14 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <AppText style={{ fontSize: 14 }}>앱 버전</AppText>
                <AppText color={colors.textMuted} style={{ fontSize: 14 }}>
                  1.0.0 (MVP)
                </AppText>
              </View>
              <View style={{ height: 1, backgroundColor: colors.border }} />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <AppText style={{ fontSize: 14 }}>개인정보 처리방침</AppText>
                <AppText color={colors.textMuted} style={{ fontSize: 14 }}>
                  기기 내 처리
                </AppText>
              </View>
            </Card>
          </View>

          <Pressable
            onPress={() =>
              Alert.alert('히스토리 새로고침', '백엔드에서 통화 기록을 다시 불러옵니다.', [
                { text: '취소', style: 'cancel' },
                { text: '새로고침', onPress: () => void fetchCalls() },
              ])
            }
          >
            <AppText weight="600" color={colors.primary} style={{ fontSize: 14, textAlign: 'center' }}>
              히스토리 새로고침
            </AppText>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
