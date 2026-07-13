import { useEffect } from 'react';
import { Platform, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useTheme } from '@/core/theme/theme';
import { useAppStore } from '@/state/appStore';
import { useCallStore } from '@/state/callStore';
import { useSettingsStore } from '@/state/settingsStore';

export default function RootLayout() {
  const hydrateSettings = useSettingsStore((s) => s.hydrate);
  const hydrateApp = useAppStore((s) => s.hydrate);
  const fetchCalls = useCallStore((s) => s.fetchCalls);
  const { colors, isDark } = useTheme();

  useEffect(() => {
    void hydrateSettings();
    void hydrateApp();
    void fetchCalls(); // 히스토리는 백엔드에서 조회
  }, [hydrateSettings, hydrateApp, fetchCalls]);

  const stack = (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="onboarding" />
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="upload" />
      <Stack.Screen name="realtime" options={{ animation: 'slide_from_bottom' }} />
      <Stack.Screen name="result" />
      <Stack.Screen name="prevention" />
      <Stack.Screen name="settings" />
      <Stack.Screen name="warning" options={{ presentation: 'transparentModal', animation: 'fade' }} />
    </Stack>
  );

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style={isDark ? 'light' : 'dark'} />
        {Platform.OS === 'web' ? (
          // 웹(데스크톱)에서는 폰처럼 가운데 모바일 폭으로 표시
          <View style={{ flex: 1, alignItems: 'center', backgroundColor: '#0C0C0E' }}>
            <View
              style={{
                flex: 1,
                width: '100%',
                maxWidth: 440,
                backgroundColor: colors.bg,
                shadowColor: '#000',
                shadowOpacity: 0.3,
                shadowRadius: 24,
              }}
            >
              {stack}
            </View>
          </View>
        ) : (
          stack
        )}
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
