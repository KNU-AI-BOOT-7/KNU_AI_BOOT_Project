import { Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Icon } from '@/components/Icon';
import { toPercent } from '@/core/utils/riskLevel';
import { evidenceBullets, recommendedAction } from '@/data/mock/infoContent';

const RED = '#E11D2A';

/** 전면 위험 경고 (강한 경고 임계값 도달 시 자동 표시). 진동/햅틱은 호출 측에서 처리. */
export default function Warning() {
  const router = useRouter();
  const params = useLocalSearchParams<{ score?: string; patterns?: string; category?: string }>();
  const score = Number(params.score ?? '0.88');
  const patterns = (params.patterns ?? '').split('|').filter(Boolean);
  const bullets = evidenceBullets(patterns).slice(0, 4);
  const advice = recommendedAction(params.category ?? '');

  const close = () => (router.canGoBack() ? router.back() : router.replace('/'));
  const goResponse = () => {
    close();
    setTimeout(() => router.push('/prevention'), 60);
  };

  return (
    <View style={{ flex: 1, backgroundColor: RED }}>
      <StatusBar style="light" />
      <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1, paddingHorizontal: 24 }}>
        <View style={{ flex: 1, alignItems: 'center', paddingTop: 20 }}>
          <View
            style={{
              width: 96,
              height: 96,
              borderRadius: 48,
              backgroundColor: 'rgba(255,255,255,0.16)',
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: 8,
            }}
          >
            <Icon name="alert-triangle" size={48} color="#FFFFFF" />
          </View>
          <AppText weight="800" color="#FFFFFF" style={{ fontSize: 31, lineHeight: 40, textAlign: 'center', marginTop: 22 }}>
            보이스피싱{'\n'}위험 감지!
          </AppText>
          <View
            style={{
              marginTop: 20,
              backgroundColor: 'rgba(0,0,0,0.24)',
              paddingHorizontal: 20,
              paddingVertical: 9,
              borderRadius: 22,
            }}
          >
            <AppText weight="700" color="#FFFFFF" style={{ fontSize: 14 }}>
              위험도 {toPercent(score)}% · 강한 경고
            </AppText>
          </View>

          <View
            style={{
              width: '100%',
              backgroundColor: 'rgba(255,255,255,0.14)',
              borderRadius: 16,
              padding: 18,
              marginTop: 26,
            }}
          >
            <AppText weight="800" color="#FFFFFF" style={{ fontSize: 15, marginBottom: 13 }}>
              탐지 근거
            </AppText>
            <View style={{ gap: 12 }}>
              {bullets.map((b, i) => (
                <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
                  <Icon name="check-circle" size={18} color="#FFFFFF" />
                  <AppText weight="600" color="#FFFFFF" style={{ fontSize: 14, flex: 1 }}>
                    {b}
                  </AppText>
                </View>
              ))}
            </View>
          </View>

          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 18 }}>
            <View style={{ marginTop: 1 }}>
              <Icon name="volume" size={18} color="#FFFFFF" />
            </View>
            <AppText weight="600" color="#FFFFFF" style={{ fontSize: 13, lineHeight: 20, flex: 1 }}>
              {advice}
            </AppText>
          </View>
        </View>

        <View style={{ gap: 11, paddingBottom: 6 }}>
          <Button title="대처 방법" variant="white" textColor={RED} onPress={goResponse} style={{ minHeight: 54 }} />
          <Pressable
            onPress={close}
            style={{
              minHeight: 52,
              borderRadius: 15,
              borderWidth: 1.5,
              borderColor: 'rgba(255,255,255,0.7)',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <AppText weight="700" color="#FFFFFF" style={{ fontSize: 15 }}>
              계속 지켜보기 (닫기)
            </AppText>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}
