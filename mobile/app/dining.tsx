import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import { Button, Card, fmtDate, Pill, SectionTitle, money } from '@/src/ui/components';
import { ChoiceRow } from '@/src/ui/Choice';
import { RequestTracker } from '@/src/ui/RequestTracker';

function toMin(t: string) {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

export default function Dining() {
  const params = useLocalSearchParams<{ restaurant_id?: string }>();
  const { snap, request } = useData();
  const p = snap.profile;
  const cat = snap.catalog;
  const [rid, setRid] = useState<string | undefined>(params.restaurant_id);
  const [date, setDate] = useState<string | undefined>();
  const [time, setTime] = useState<string | undefined>();
  const [size, setSize] = useState<string | undefined>();
  const [reqId, setReqId] = useState<string | null>(null);
  if (!p || !cat) return null;
  const r = p.reservation;
  const list = cat.dining.filter((d) => d.ships === '*' || (d.ships as string[]).includes(r.ship_code));
  const sel = list.find((d) => d.id === rid) ?? list[0];
  const nights = r.ports.slice(0, -1);
  const n = Number(size ?? r.party_size);
  const night = date ?? nights[0].date;
  // Fully booked seatings for this restaurant and night, synced with the offers.
  const full = new Set(snap.offers?.dining_full?.[sel.id]?.[night] ?? []);
  const open = cat.dining_times.filter((t) => !full.has(t));
  // Keep the guest's pick if it's open; otherwise the open seating closest to 7pm.
  const byPreference = [...open].sort((a, b) => Math.abs(toMin(a) - 19 * 60) - Math.abs(toMin(b) - 19 * 60));
  const slot = time && !full.has(time) ? time : byPreference[0];

  const submit = async () => {
    if (!slot) return;
    const req = await request('reserve_specialty_dining', { restaurant_id: sel.id, date: night, time: slot, party_size: n }, `${sel.name} · ${fmtDate(night)} ${slot}`);
    setReqId(req._id);
  };

  return (
    <ScrollView contentContainerStyle={styles.body}>
      {reqId ? (
        <RequestTracker id={reqId} onRetry={() => setReqId(null)} retryLabel="Pick another time" />
      ) : (
        <>
          <SectionTitle title={`Restaurants on ${r.ship_name}`} />
          <ChoiceRow options={list.map((d) => ({ value: d.id, label: d.name }))} value={sel.id} onChange={setRid} />
          <Card style={{ padding: 16, gap: 6, marginTop: 10 }}>
            <Text style={styles.h2}>{sel.name}</Text>
            <Text style={styles.meta}>{sel.cuisine} · {money(sel.price_pp)} per guest</Text>
            {p.preferences.celebration && sel.tags.includes('celebration') ? <Pill label={`Great for your ${p.preferences.celebration}`} tone="accent" icon="gift" /> : null}
            {p.preferences.dietary.length ? <Text style={styles.meta}>We'll share your dietary notes: {p.preferences.dietary.join(', ')}</Text> : null}
          </Card>
          <SectionTitle title="Night" />
          <ChoiceRow options={nights.map((d) => ({ value: d.date, label: `${fmtDate(d.date, { weekday: 'short', day: 'numeric' })} · ${d.port.split(',')[0]}` }))} value={night} onChange={setDate} />
          <SectionTitle title="Time" />
          <ChoiceRow options={cat.dining_times.map((t) => ({ value: t, label: t, disabled: full.has(t) }))} value={slot} onChange={setTime} />
          <Text style={styles.tiny}>
            {open.length ? (full.size ? `Greyed-out times are fully booked that night.` : 'Every seating is open that night.') : 'Fully booked that night - pick another night.'}
          </Text>
          <SectionTitle title="Guests" />
          <ChoiceRow options={Array.from({ length: Math.max(r.party_size, 2) + 2 }, (_, i) => String(i + 1)).map((v) => ({ value: v, label: v }))} value={String(n)} onChange={setSize} />
          <Card style={{ padding: 16, marginTop: 18, gap: 10 }}>
            <Text style={styles.total}>{money(sel.price_pp * n)}</Text>
            <Button label="Reserve table" icon="restaurant" disabled={!slot} onPress={() => void submit()} />
            <Text style={styles.tiny}>Saved to Couchbase Lite first - confirmed when it syncs.</Text>
          </Card>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  h2: { fontSize: theme.type.xl, fontWeight: '700', fontFamily: theme.font.display, color: theme.color.princess },
  meta: { color: theme.color.muted, fontSize: theme.type.sm },
  total: { fontSize: 30, fontWeight: '900', color: theme.color.navy, textAlign: 'center' },
  tiny: { color: theme.color.faint, fontSize: theme.type.xs, textAlign: 'center' },
});
