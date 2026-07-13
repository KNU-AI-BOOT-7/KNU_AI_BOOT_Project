import { ActivityIndicator, View } from 'react-native';
import { Redirect, Tabs } from 'expo-router';
import { Icon } from '@/components/Icon';
import { useTheme } from '@/core/theme/theme';
import { useAppStore } from '@/state/appStore';

export default function TabsLayout() {
  const { colors } = useTheme();
  const onboarded = useAppStore((s) => s.onboarded);

  if (onboarded === null) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  if (!onboarded) {
    return <Redirect href="/onboarding" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          height: 64,
          paddingTop: 6,
          paddingBottom: 10,
        } as never,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '홈',
          tabBarIcon: ({ color }) => <Icon name="home" size={22} color={color as string} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: '히스토리',
          tabBarIcon: ({ color }) => <Icon name="clock" size={22} color={color as string} />,
        }}
      />
      <Tabs.Screen
        name="info"
        options={{
          title: '정보',
          tabBarIcon: ({ color }) => <Icon name="info" size={22} color={color as string} />,
        }}
      />
    </Tabs>
  );
}
