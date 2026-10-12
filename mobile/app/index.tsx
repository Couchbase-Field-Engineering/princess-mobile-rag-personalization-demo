import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { useAuth } from '@/src/session/AuthContext';
import { theme } from '@/src/theme';

export default function Index() {
  const { ready, session } = useAuth();
  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.navy }}>
        <ActivityIndicator color={theme.color.gold} />
      </View>
    );
  }
  return <Redirect href={session ? '/(tabs)' : '/login'} />;
}
