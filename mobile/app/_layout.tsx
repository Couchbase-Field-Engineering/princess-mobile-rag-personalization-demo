import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { DataProvider } from '@/src/data/DataContext';
import { AuthProvider } from '@/src/session/AuthContext';
import { theme } from '@/src/theme';
import { DeviceFrame } from '@/src/ui/DeviceFrame';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <DataProvider>
          <DeviceFrame>
            <StatusBar style="light" />
            <Stack
              screenOptions={{
                headerStyle: { backgroundColor: theme.color.navy },
                headerTintColor: theme.color.onDark,
                headerTitleStyle: { fontWeight: '800' },
                contentStyle: { backgroundColor: theme.color.bg },
              }}
            >
              <Stack.Screen name="index" options={{ headerShown: false }} />
              <Stack.Screen name="login" options={{ headerShown: false }} />
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
              <Stack.Screen name="upgrade" options={{ title: 'Upgrade your stateroom', presentation: 'modal' }} />
              <Stack.Screen name="dining" options={{ title: 'Specialty dining', presentation: 'modal' }} />
              <Stack.Screen name="spa" options={{ title: 'Vitality Spa', presentation: 'modal' }} />
              <Stack.Screen name="checkin" options={{ title: 'Online check-in', presentation: 'modal' }} />
              <Stack.Screen name="confirm" options={{ title: 'Review & confirm', presentation: 'modal' }} />
            </Stack>
          </DeviceFrame>
        </DataProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
