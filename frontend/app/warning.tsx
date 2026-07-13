import { Pressable, StyleSheet, View } from 'react-native';
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

  // 경고는 항상 /realtime에서 push되어 열린다. canGoBack()이 어떤 이유로든 false면
  // (예: 새로고침으로 히스토리가 끊긴 경우) 홈으로 보내면 진행 중이던 실시간 세션이
  // 그대로 끊겨버리므로, 홈 대신 realtime으로 돌아가게 한다.
  const close = () => (router.canGoBack() ? router.back() : router.replace('/realtime'));
  const goResponse = () => {
    close();
    setTimeout(() => router.push('/prevention'), 60);
  };

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.55)',
        justifyContent: 'center',
        paddingHorizontal: 20,
      }}
    >
      <StatusBar style="light" />
      {/* 배경(뒤 화면 비침) 탭 시 닫기 */}
      <Pressable style={StyleSheet.absoluteFill} onPress={close} accessibilityLabel="경고 닫기" />

      {/* 중앙 팝업 카드 */}
      <View
        style={{
          width: '100%',
          backgroundColor: RED,
          borderRadius: 28,
          paddingHorizontal: 22,
          paddingTop: 26,
          paddingBottom: 18,
          alignItems: 'center',
          shadowColor: '#000',
          shadowOpacity: 0.4,
          shadowRadius: 24,
          shadowOffset: { width: 0, height: 12 },
          elevation: 12,
        }}
      >
        <View
          style={{
            width: 74,
            height: 74,
            borderRadius: 37,
            backgroundColor: 'rgba(255,255,255,0.16)',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="alert-triangle" size={38} color="#FFFFFF" />
        </View>
        <AppText weight="800" color="#FFFFFF" style={{ fontSize: 26, lineHeight: 34, textAlign: 'center', marginTop: 16 }}>
          보이스피싱{'\n'}위험 감지!
        </AppText>
        <View
          style={{
            marginTop: 14,
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
            padding: 16,
            marginTop: 20,
          }}
        >
          <AppText weight="800" color="#FFFFFF" style={{ fontSize: 15, marginBottom: 12 }}>
            탐지 근거
          </AppText>
          <View style={{ gap: 11 }}>
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

        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 14 }}>
          <View style={{ marginTop: 1 }}>
            <Icon name="volume" size={18} color="#FFFFFF" />
          </View>
          <AppText weight="600" color="#FFFFFF" style={{ fontSize: 13, lineHeight: 20, flex: 1 }}>
            {advice}
          </AppText>
        </View>

        <View style={{ width: '100%', gap: 10, marginTop: 22 }}>
          <Button title="대처 방법" variant="white" textColor={RED} onPress={goResponse} style={{ minHeight: 52 }} />
          <Pressable
            onPress={close}
            style={{
              minHeight: 50,
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
      </View>
    </View>
  );
}
