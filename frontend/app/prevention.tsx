import { Linking, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon } from '@/components/Icon';
import { IconCircle } from '@/components/IconCircle';
import { useTheme } from '@/core/theme/theme';
import { FSS_REPORT_NUMBER, PREVENTION_TYPES, THREE_SECOND_RULE } from '@/data/mock/infoContent';

export default function Prevention() {
  const { colors } = useTheme();
  const router = useRouter();

  return (
    <View style={{ flex: 1, backgroundColor: colors.primary }}>
      <StatusBar style="light" />
      <SafeAreaView edges={['top']}>
        <View style={{ paddingHorizontal: 22, paddingBottom: 22 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 }}>
            <Pressable hitSlop={10} onPress={() => (router.canGoBack() ? router.back() : router.replace('/info'))}>
              <Icon name="chevron-left" size={26} color="#FFFFFF" />
            </Pressable>
            <AppText weight="700" color="#FFFFFF" style={{ fontSize: 16 }}>
              예방 정보
            </AppText>
          </View>
          <AppText weight="800" color="#FFFFFF" style={{ fontSize: 25, lineHeight: 33, marginTop: 4 }}>
            알아두면{'\n'}당하지 않습니다
          </AppText>
          <AppText weight="600" color="rgba(255,255,255,0.9)" style={{ fontSize: 13, marginTop: 9 }}>
            보이스피싱 3대 유형과 대응 요령
          </AppText>
        </View>
      </SafeAreaView>

      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          borderTopLeftRadius: 26,
          borderTopRightRadius: 26,
        }}
      >
        <ScrollView
          contentContainerStyle={{ padding: 20, gap: 12 }}
          showsVerticalScrollIndicator={false}
        >
          {PREVENTION_TYPES.map((t, i) => {
            const tone =
              t.tone === 'warning'
                ? { c: colors.warningText, bg: colors.warningFaint }
                : { c: colors.danger, bg: colors.dangerFaint };
            return (
              <Card key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 13 }}>
                <IconCircle name="shield-alert" color={tone.c} bg={tone.bg} size={42} radius={12} iconSize={21} />
                <View style={{ flex: 1 }}>
                  <AppText weight="700" style={{ fontSize: 15 }}>
                    {t.title}
                  </AppText>
                  <AppText color={colors.textMuted} style={{ fontSize: 12, marginTop: 2 }}>
                    {t.desc}
                  </AppText>
                </View>
              </Card>
            );
          })}

          <View style={{ backgroundColor: colors.safeFaint, borderRadius: 14, padding: 16 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 7 }}>
              <Icon name="check-circle" size={18} color={colors.safeText} />
              <AppText weight="800" color={colors.safeText} style={{ fontSize: 15 }}>
                3초 대응 원칙
              </AppText>
            </View>
            <AppText weight="500" color={colors.safeText} style={{ fontSize: 12.5, lineHeight: 20 }}>
              {THREE_SECOND_RULE}
            </AppText>
          </View>

          <Pressable onPress={() => Linking.openURL(`tel:${FSS_REPORT_NUMBER}`)} style={{ marginTop: 4 }}>
            <View
              style={{
                backgroundColor: colors.primary,
                borderRadius: 15,
                minHeight: 54,
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 9,
              }}
            >
              <Icon name="phone" size={19} color="#FFFFFF" />
              <AppText weight="700" color="#FFFFFF" style={{ fontSize: 15.5 }}>
                금융감독원 신고 {FSS_REPORT_NUMBER}
              </AppText>
            </View>
          </Pressable>
        </ScrollView>
      </View>
    </View>
  );
}
