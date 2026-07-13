import { useState } from 'react';
import { Switch, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Icon, type IconName } from '@/components/Icon';
import { IconCircle } from '@/components/IconCircle';
import { InfoBanner } from '@/components/InfoBanner';
import { useTheme } from '@/core/theme/theme';
import { useAppStore } from '@/state/appStore';

function PermRow({
  icon,
  iconColor,
  iconBg,
  title,
  desc,
  value,
  onChange,
  cardBg,
  textColor,
  subColor,
}: {
  icon: IconName;
  iconColor: string;
  iconBg: string;
  title: string;
  desc: string;
  value: boolean;
  onChange: (v: boolean) => void;
  cardBg: string;
  textColor: string;
  subColor: string;
}) {
  return (
    <View
      style={{
        backgroundColor: cardBg,
        borderRadius: 16,
        padding: 15,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 13,
      }}
    >
      <IconCircle name={icon} color={iconColor} bg={iconBg} size={42} radius={12} iconSize={21} />
      <View style={{ flex: 1 }}>
        <AppText weight="700" color={textColor} style={{ fontSize: 15 }}>
          {title}
        </AppText>
        <AppText color={subColor} style={{ fontSize: 12.5, marginTop: 2 }}>
          {desc}
        </AppText>
      </View>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

export default function Onboarding() {
  const { colors } = useTheme();
  const router = useRouter();
  const complete = useAppStore((s) => s.completeOnboarding);
  const [mic, setMic] = useState(true);
  const [noti, setNoti] = useState(true);

  const onStart = () => {
    complete();
    router.replace('/');
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.primary }}>
      <StatusBar style="light" />
      <SafeAreaView edges={['top']}>
        <View style={{ alignItems: 'center', paddingHorizontal: 24, paddingTop: 26, paddingBottom: 30 }}>
          <View
            style={{
              width: 66,
              height: 66,
              borderRadius: 20,
              backgroundColor: 'rgba(255,255,255,0.18)',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <Icon name="shield-check" size={36} color="#FFFFFF" />
          </View>
          <AppText weight="800" color="#FFFFFF" style={{ fontSize: 27, letterSpacing: -0.5 }}>
            VoiceGuard AI
          </AppText>
          <AppText
            weight="600"
            color="rgba(255,255,255,0.92)"
            style={{ fontSize: 13.5, lineHeight: 21, textAlign: 'center', marginTop: 9 }}
          >
            통화 속 보이스피싱을 실시간으로{'\n'}탐지하고 경고하는 보안 도우미
          </AppText>
        </View>
      </SafeAreaView>

      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          borderTopLeftRadius: 26,
          borderTopRightRadius: 26,
          padding: 22,
        }}
      >
        <AppText weight="700" color={colors.textSecondary} style={{ fontSize: 14, marginBottom: 12 }}>
          시작하려면 아래 권한이 필요해요
        </AppText>
        <View style={{ gap: 12 }}>
          <PermRow
            icon="mic"
            iconColor={colors.primary}
            iconBg={colors.primaryFaint}
            title="마이크 권한"
            desc="통화 음성을 분석합니다"
            value={mic}
            onChange={setMic}
            cardBg={colors.card}
            textColor={colors.text}
            subColor={colors.textMuted}
          />
          <PermRow
            icon="bell"
            iconColor={colors.warningText}
            iconBg={colors.warningFaint}
            title="알림 권한"
            desc="위험 감지 시 즉시 경고합니다"
            value={noti}
            onChange={setNoti}
            cardBg={colors.card}
            textColor={colors.text}
            subColor={colors.textMuted}
          />
        </View>
        <View style={{ marginTop: 16 }}>
          <InfoBanner
            icon="lock"
            text="음성은 분석 목적으로만 사용되며 기기와 서버에 안전하게 처리됩니다."
          />
        </View>

        <View style={{ flex: 1 }} />
        <Button title="권한 허용하고 시작하기" onPress={onStart} style={{ minHeight: 56 }} />
        <View style={{ height: 16 }} />
      </View>
    </View>
  );
}
