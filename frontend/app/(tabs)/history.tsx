import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { AppText } from '@/components/AppText';
import { CallCard } from '@/components/CallCard';
import { Card } from '@/components/Card';
import { useTheme } from '@/core/theme/theme';
import { riskColorText, riskColorFaint, riskLevelFromScore, type RiskLevel } from '@/core/utils/riskLevel';
import { callSource } from '@/data/services/callsApi';
import { useCallStore } from '@/state/callStore';
import { useSettingsStore } from '@/state/settingsStore';

type Filter = 'all' | RiskLevel;

export default function History() {
  const { colors } = useTheme();
  const router = useRouter();
  const calls = useCallStore((s) => s.calls);
  const loading = useCallStore((s) => s.loading);
  const error = useCallStore((s) => s.error);
  const fetchCalls = useCallStore((s) => s.fetchCalls);
  const dangerThreshold = useSettingsStore((s) => s.dangerThreshold);
  const [filter, setFilter] = useState<Filter>('all');

  // 탭에 진입할 때마다 백엔드에서 최신 히스토리를 다시 받아온다.
  useFocusEffect(
    useCallback(() => {
      void fetchCalls();
    }, [fetchCalls]),
  );

  const withLevel = calls.map((c) => ({
    c,
    level: riskLevelFromScore(c.risk_score, dangerThreshold),
  }));
  const counts = {
    danger: withLevel.filter((x) => x.level === 'danger').length,
    warning: withLevel.filter((x) => x.level === 'warning').length,
    safe: withLevel.filter((x) => x.level === 'safe').length,
  };
  const shown = withLevel.filter((x) => filter === 'all' || x.level === filter);

  const boxes: { key: RiskLevel; label: string; count: number }[] = [
    { key: 'danger', label: '위험', count: counts.danger },
    { key: 'warning', label: '주의', count: counts.warning },
    { key: 'safe', label: '정상', count: counts.safe },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        <View style={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 14 }}>
          <AppText weight="800" style={{ fontSize: 26 }}>
            히스토리
          </AppText>
        </View>

        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24, gap: 12 }}
          showsVerticalScrollIndicator={false}
        >
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {boxes.map((b) => {
              const active = filter === b.key;
              const textCol = riskColorText(b.key, colors);
              return (
                <Pressable
                  key={b.key}
                  style={{ flex: 1 }}
                  onPress={() => setFilter(active ? 'all' : b.key)}
                >
                  <View
                    style={{
                      backgroundColor: riskColorFaint(b.key, colors),
                      borderRadius: 14,
                      paddingVertical: 16,
                      alignItems: 'center',
                      borderWidth: 2,
                      borderColor: active ? textCol : 'transparent',
                    }}
                  >
                    <AppText weight="800" color={textCol} style={{ fontSize: 24 }}>
                      {b.count}
                    </AppText>
                    <AppText weight="600" color={textCol} style={{ fontSize: 12.5, marginTop: 2 }}>
                      {b.label}
                    </AppText>
                  </View>
                </Pressable>
              );
            })}
          </View>

          {filter !== 'all' ? (
            <Pressable onPress={() => setFilter('all')} style={{ alignSelf: 'flex-start' }}>
              <AppText weight="600" color={colors.primary} style={{ fontSize: 13 }}>
                전체 보기 ✕
              </AppText>
            </Pressable>
          ) : null}

          {error && calls.length === 0 ? (
            <Card>
              <AppText color={colors.danger} style={{ fontSize: 13, textAlign: 'center', lineHeight: 20 }}>
                히스토리를 불러오지 못했습니다.{'\n'}{error}
              </AppText>
              <Pressable onPress={() => void fetchCalls()} style={{ marginTop: 10 }}>
                <AppText weight="700" color={colors.primary} style={{ fontSize: 14, textAlign: 'center' }}>
                  다시 시도
                </AppText>
              </Pressable>
            </Card>
          ) : loading && calls.length === 0 ? (
            <View style={{ paddingVertical: 40, alignItems: 'center' }}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : shown.length === 0 ? (
            <Card>
              <AppText color={colors.textMuted} style={{ fontSize: 13, textAlign: 'center' }}>
                해당하는 통화 내역이 없습니다.
              </AppText>
            </Card>
          ) : (
            shown.map(({ c }) => (
              <CallCard
                key={c.id}
                category={c.phishing_type || '분석 결과'}
                score={c.risk_score}
                source={callSource(c.file_type)}
                createdAt={c.called_at}
                onPress={() => router.push(`/result?id=${c.id}`)}
              />
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
