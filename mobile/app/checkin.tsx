import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import { Button, Card, fmtDate, SectionTitle } from '@/src/ui/components';
import { ChoiceRow } from '@/src/ui/Choice';
import { RequestTracker } from '@/src/ui/RequestTracker';

export default function CheckIn() {
  const { snap, request } = useData();
  const [slot, setSlot] = useState<string | undefined>();
  const [docs, setDocs] = useState(false);
  const [reqId, setReqId] = useState<string | null>(null);
  const p = snap.profile;
  if (!p || !snap.catalog) return null;
  const r = p.reservation;

  const submit = async () => {
    const req = await request('complete_online_checkin', { arrival_slot: slot }, `Check-in · arrival ${slot}`);
    setReqId(req._id);
  };

  return (
    <ScrollView contentContainerStyle={styles.body}>
      {reqId ? <RequestTracker id={reqId} onRetry={() => setReqId(null)} /> : (
        <>
          <Card style={{ padding: 16, gap: 4 }}>
            <Text style={styles.h2}>{r.ship_name}</Text>
            <Text style={styles.meta}>{fmtDate(r.embark_date, { weekday: 'long', month: 'long', day: 'numeric' })} · {r.embark_port}</Text>
            <Text style={styles.meta}>Checking in {r.party_size} guest{r.party_size > 1 ? 's' : ''}: {r.party.map((m) => m.name).join(', ')}</Text>
          </Card>
          <SectionTitle title="Terminal arrival time" />
          <ChoiceRow options={snap.catalog.arrival_slots.map((t) => ({ value: t, label: t }))} value={slot} onChange={setSlot} />
          <Pressable onPress={() => setDocs(!docs)} style={styles.check}>
            <Ionicons name={docs ? 'checkbox' : 'square-outline'} size={22} color={theme.color.royal} />
            <Text style={{ flex: 1, color: theme.color.text }}>Everyone in my party has valid travel documents and I've reviewed the health & safety questions.</Text>
          </Pressable>
          <View style={{ marginTop: 16 }}>
            <Button label="Complete check-in" icon="qr-code" disabled={!slot || !docs} onPress={() => void submit()} />
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  h2: { fontSize: theme.type.xl, fontWeight: '900', color: theme.color.navy },
  meta: { color: theme.color.muted, fontSize: theme.type.sm },
  check: { flexDirection: 'row', gap: 10, alignItems: 'center', marginTop: 18, backgroundColor: theme.color.surface, padding: 14, borderRadius: theme.radiusSm },
});
