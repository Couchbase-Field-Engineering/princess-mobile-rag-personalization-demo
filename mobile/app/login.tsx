import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { api, type Persona } from '@/src/api';
import { API_URL } from '@/src/config';
import { useAuth } from '@/src/session/AuthContext';
import { theme } from '@/src/theme';
import { Button, fmtDate, Pill, Wordmark } from '@/src/ui/components';

const FALLBACK: Persona[] = [
  { guest_id: 'G00000101', name: 'Olivia Bennett', last_name: 'Bennett', booking_id: '4810101', ship: 'Sun Princess', embark_date: '', days_to_sail: 9, tier: 'Elite', stateroom: 'Balcony', blurb: 'Elite member celebrating an anniversary.' },
  { guest_id: 'G00000201', name: 'Carlos Rivera', last_name: 'Rivera', booking_id: '4820202', ship: 'Caribbean Princess', embark_date: '', days_to_sail: 3, tier: 'Gold', stateroom: 'Interior', blurb: 'Family of four on a weekend getaway.' },
  { guest_id: 'G00000301', name: 'Priya Natarajan', last_name: 'Natarajan', booking_id: '4830303', ship: 'Star Princess', embark_date: '', days_to_sail: 2, tier: 'Platinum', stateroom: 'Mini-Suite', blurb: 'Solo wellness traveler.' },
];

export default function Login() {
  const { session, signIn, notice } = useAuth();
  const insets = useSafeAreaInsets();
  const [booking, setBooking] = useState('');
  const [last, setLast] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>(FALLBACK);

  useEffect(() => {
    api<{ personas: Persona[] }>('/api/demo/personas', { timeoutMs: 5000 })
      .then((r) => r.personas.length && setPersonas(r.personas))
      .catch(() => {});
  }, []);

  if (session) return <Redirect href="/(tabs)" />;

  const go = async (b = booking, l = last) => {
    setBusy(true);
    setErr(null);
    try {
      await signIn(b, l);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <LinearGradient colors={theme.gradient.hero as unknown as [string, string]} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={[styles.wrap, { paddingTop: insets.top + 32, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
          <Wordmark size={17} />
          <Text style={styles.hero}>Your vacation,{'\n'}made just for you.</Text>
          <Text style={styles.sub}>Sign in with your reservation to see offers picked for you, plan every day and chat with your concierge - even at sea with no signal.</Text>

          <View style={styles.form}>
            {notice ? (
              <View style={styles.notice}>
                <Ionicons name="time-outline" size={16} color={theme.color.navy} />
                <Text style={styles.noticeText}>{notice}</Text>
              </View>
            ) : null}
            <Text style={styles.label}>RESERVATION NUMBER</Text>
            <TextInput value={booking} onChangeText={setBooking} placeholder="e.g. 4810101" placeholderTextColor={theme.color.faint} style={styles.input} keyboardType="number-pad" />
            <Text style={styles.label}>LAST NAME</Text>
            <TextInput value={last} onChangeText={setLast} placeholder="e.g. Bennett" placeholderTextColor={theme.color.faint} style={styles.input} autoCapitalize="words" />
            {err ? <Text style={styles.err}>{err}</Text> : null}
            <Button label="Find my cruise" onPress={() => void go()} busy={busy} disabled={!booking || !last} icon="search" />
          </View>

          <Text style={[styles.label, { color: theme.color.onDarkMuted, marginTop: 28 }]}>DEMO GUESTS · FROM TODAY'S ADOBE REAL-TIME CDP EXPORT</Text>
          {personas.map((p) => (
            <Pressable key={p.guest_id} onPress={() => void go(p.booking_id, p.last_name)} style={({ pressed }) => [styles.persona, pressed && { opacity: 0.8 }]}>
              <View style={styles.avatar}>
                <Text style={{ color: theme.color.princess, fontWeight: '900' }}>{p.name.split(' ').map((s) => s[0]).join('')}</Text>
              </View>
              <View style={{ flex: 1, gap: 3 }}>
                <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Text style={styles.pname}>{p.name}</Text>
                  <Pill label={p.tier} tone="gold" />
                </View>
                <Text style={styles.pmeta}>
                  {p.ship} · {p.embark_date ? fmtDate(p.embark_date) : ''} · {p.stateroom} · #{p.booking_id}
                </Text>
                <Text style={styles.pblurb}>{p.blurb}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={theme.color.onDarkMuted} />
            </Pressable>
          ))}
          <Text style={styles.foot}>Backend: {API_URL}</Text>
        </ScrollView>
      </LinearGradient>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: 22, gap: 10, maxWidth: 520, width: '100%', alignSelf: 'center' },
  hero: { color: theme.color.onDark, fontSize: theme.type.hero, fontWeight: '700', fontFamily: theme.font.display, marginTop: 28, lineHeight: 40 },
  sub: { color: theme.color.onDarkMuted, fontSize: theme.type.md, lineHeight: 21 },
  form: { backgroundColor: theme.color.surface, borderRadius: theme.radius, padding: 18, gap: 8, marginTop: 18 },
  label: { color: theme.color.muted, fontSize: theme.type.xs, fontWeight: '800', letterSpacing: 1.3 },
  input: { borderWidth: 1, borderColor: theme.color.border, borderRadius: theme.radiusSm, padding: 13, fontSize: theme.type.lg, color: theme.color.text, marginBottom: 6 },
  err: { color: theme.color.danger, fontWeight: '600' },
  notice: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: '#FFF4D6', borderRadius: theme.radiusSm, padding: 10, marginBottom: 6 },
  noticeText: { flex: 1, color: theme.color.navy, fontWeight: '600', fontSize: theme.type.sm },
  persona: { flexDirection: 'row', gap: 12, alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: theme.radius, padding: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)' },
  avatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: theme.color.oceanSoft, alignItems: 'center', justifyContent: 'center' },
  pname: { color: theme.color.onDark, fontWeight: '800', fontSize: theme.type.md },
  pmeta: { color: theme.color.onDarkMuted, fontSize: theme.type.sm },
  pblurb: { color: 'rgba(255,255,255,0.88)', fontSize: theme.type.sm },
  foot: { color: 'rgba(255,255,255,0.4)', fontSize: theme.type.xs, marginTop: 16, textAlign: 'center' },
});
