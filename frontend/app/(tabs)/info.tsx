import { Linking, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon } from '@/components/Icon';
import { IconCircle } from '@/components/IconCircle';
import { useTheme } from '@/core/theme/theme';
import { FSS_REPORT_NUMBER, TYPE_RESPONSES, URGENT_STEPS } from '@/data/mock/infoContent';

export default function Info() {
  const { colors } = useTheme();
  const router = useRouter();

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <View style={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12 }}>
          <AppText weight="800" style={{ fontSize: 24 }}>
            정보
          </AppText>
          <AppText color={colors.textMuted} style={{ fontSize: 13, marginTop: 3 }}>
            보이스피싱 대응 방법을 확인하세요
          </AppText>
        </View>

        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24, gap: 16 }}
          showsVerticalScrollIndicator={false}
        >
          {/* 지금 의심 통화 중이라면 */}
          <View
            style={{
              backgroundColor: colors.primary,
              borderRadius: 16,
              padding: 17,
            }}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 13 }}>
              <Icon name="shield-check" size={18} color="#FFFFFF" />
              <AppText weight="800" color="#FFFFFF" style={{ fontSize: 15 }}>
                지금 의심 통화 중이라면
              </AppText>
            </View>
            <View style={{ gap: 12 }}>
              {URGENT_STEPS.map((s, i) => (
                <View key={i} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
                  <View
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 10,
                      backgroundColor: 'rgba(255,255,255,0.25)',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginTop: 1,
                    }}
                  >
                    <AppText weight="800" color="#FFFFFF" style={{ fontSize: 11 }}>
                      {i + 1}
                    </AppText>
                  </View>
                  <AppText weight="600" color="#FFFFFF" style={{ fontSize: 13, lineHeight: 20, flex: 1 }}>
                    {s}
                  </AppText>
                </View>
              ))}
            </View>
          </View>

          <AppText weight="800" style={{ fontSize: 16 }}>
            유형별 대응 방법
          </AppText>

          {TYPE_RESPONSES.map((t, i) => {
            const tone = t.title.includes('대출')
              ? { c: colors.warningText, bg: colors.warningFaint }
              : { c: colors.danger, bg: colors.dangerFaint };
            return (
              <Card key={i}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 9 }}>
                  <IconCircle name="shield-alert" color={tone.c} bg={tone.bg} size={34} radius={9} iconSize={18} />
                  <AppText weight="700" style={{ fontSize: 15 }}>
                    {t.title}
                  </AppText>
                </View>
                <AppText color={colors.textSecondary} style={{ fontSize: 12.5, lineHeight: 20 }}>
                  {t.body}
                </AppText>
              </Card>
            );
          })}

          <Pressable onPress={() => router.push('/prevention')}>
            <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 13 }}>
              <IconCircle name="shield-check" color={colors.primary} bg={colors.primaryFaint} size={40} radius={12} iconSize={20} />
              <View style={{ flex: 1 }}>
                <AppText weight="700" style={{ fontSize: 15 }}>
                  보이스피싱 예방 정보
                </AppText>
                <AppText color={colors.textMuted} style={{ fontSize: 12.5, marginTop: 2 }}>
                  3대 유형과 3초 대응 원칙 알아보기
                </AppText>
              </View>
              <Icon name="chevron-right" size={20} color={colors.textMuted} />
            </Card>
          </Pressable>

          <Pressable onPress={() => Linking.openURL(`tel:${FSS_REPORT_NUMBER}`)}>
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
      </SafeAreaView>
    </View>
  );
}
