import { useCallback } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppText } from '@/components/AppText';
import { CallCard } from '@/components/CallCard';
import { Card } from '@/components/Card';
import { Icon, type IconName } from '@/components/Icon';
import { IconCircle } from '@/components/IconCircle';
import { useTheme } from '@/core/theme/theme';
import { riskLevelFromScore } from '@/core/utils/riskLevel';
import { callSource } from '@/data/services/callsApi';
import { useCallStore } from '@/state/callStore';
import { useSettingsStore } from '@/state/settingsStore';

function EntryCard({
  icon,
  iconColor,
  iconBg,
  title,
  desc,
  onPress,
}: {
  icon: IconName;
  iconColor: string;
  iconBg: string;
  title: string;
  desc: string;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  return (
    <Pressable onPress={onPress} android_ripple={{ color: 'rgba(0,0,0,0.05)' }}>
      <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 13 }}>
        <IconCircle name={icon} color={iconColor} bg={iconBg} size={44} radius={12} iconSize={22} />
        <View style={{ flex: 1 }}>
          <AppText weight="700" style={{ fontSize: 15.5 }}>
            {title}
          </AppText>
          <AppText color={colors.textMuted} style={{ fontSize: 12.5, marginTop: 2 }}>
            {desc}
          </AppText>
        </View>
        <Icon name="chevron-right" size={20} color={colors.textMuted} />
      </Card>
    </Pressable>
  );
}

export default function Home() {
  const { colors } = useTheme();
  const router = useRouter();
  const calls = useCallStore((s) => s.calls);
  const fetchCalls = useCallStore((s) => s.fetchCalls);
  const dangerThreshold = useSettingsStore((s) => s.dangerThreshold);

  // 홈에 돌아올 때마다 최신 히스토리 반영
  useFocusEffect(
    useCallback(() => {
      void fetchCalls();
    }, [fetchCalls]),
  );

  const now = new Date();
  const monthDanger = calls.filter((c) => {
    const d = new Date(c.called_at);
    const sameMonth = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    return sameMonth && riskLevelFromScore(c.risk_score, dangerThreshold) !== 'safe';
  }).length;

  const recent = calls.slice(0, 3);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <StatusBar style="light" />
      {/* 파란 헤더 */}
      <View style={{ backgroundColor: colors.primary }}>
        <SafeAreaView edges={['top']}>
          <View style={{ paddingHorizontal: 22, paddingTop: 6 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
                <Icon name="shield-check" size={24} color="#FFFFFF" />
                <AppText weight="800" color="#FFFFFF" style={{ fontSize: 19, letterSpacing: -0.4 }}>
                  VoiceGuard AI
                </AppText>
              </View>
              <Pressable hitSlop={10} onPress={() => router.push('/settings')} accessibilityLabel="설정">
                <Icon name="settings" size={23} color="#FFFFFF" />
              </Pressable>
            </View>
            <View style={{ paddingTop: 16, paddingBottom: 26 }}>
              <AppText weight="500" color="rgba(255,255,255,0.9)" style={{ fontSize: 13 }}>
                이번 달 안전하게 지켜드렸어요
              </AppText>
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', marginTop: 6 }}>
                <AppText weight="800" color="#FFFFFF" style={{ fontSize: 40, letterSpacing: -1 }}>
                  {monthDanger}
                </AppText>
                <AppText weight="600" color="#FFFFFF" style={{ fontSize: 16, marginLeft: 5, marginBottom: 6 }}>
                  건 위험 통화 탐지
                </AppText>
              </View>
            </View>
          </View>
        </SafeAreaView>
      </View>

      <ScrollView
        style={{ flex: 1, marginTop: -14 }}
        contentContainerStyle={{ padding: 20, paddingTop: 0, gap: 12 }}
        showsVerticalScrollIndicator={false}
      >
        <EntryCard
          icon="activity"
          iconColor={colors.primary}
          iconBg={colors.primaryFaint}
          title="실시간 통화 감지"
          desc="지금 통화를 감지합니다"
          onPress={() => router.push('/realtime')}
        />
        <EntryCard
          icon="upload"
          iconColor={colors.accentViolet}
          iconBg={colors.accentVioletFaint}
          title="음성 파일 분석"
          desc="녹음 파일을 업로드합니다"
          onPress={() => router.push('/upload')}
        />

        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: 6,
            paddingHorizontal: 2,
          }}
        >
          <AppText weight="800" style={{ fontSize: 16 }}>
            최근 분석 내역
          </AppText>
          <Pressable onPress={() => router.push('/history')} hitSlop={8}>
            <AppText weight="600" color={colors.primary} style={{ fontSize: 13 }}>
              전체보기
            </AppText>
          </Pressable>
        </View>

        {recent.length === 0 ? (
          <Card>
            <AppText color={colors.textMuted} style={{ fontSize: 13, textAlign: 'center' }}>
              아직 분석 내역이 없습니다.
            </AppText>
          </Card>
        ) : (
          recent.map((c) => (
            <CallCard
              key={c.id}
              category={c.phishing_type || '분석 결과'}
              score={c.risk_score}
              source={callSource(c.file_type)}
              createdAt={c.called_at}
              showMeta={false}
              onPress={() => router.push(`/result?id=${c.id}`)}
            />
          ))
        )}
      </ScrollView>
    </View>
  );
}
