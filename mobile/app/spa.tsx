import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import { Button, Card, fmtDate, Pill, SectionTitle, money } from '@/src/ui/components';
import { ChoiceRow } from '@/src/ui/Choice';
import { RequestTracker } from '@/src/ui/RequestTracker';

const TIMES = ['09:00', '10:00', '11:30', '13:00', '14:30', '16:00', '17:30'];

export default function Spa() {
  const params = useLocalSearchParams<{ treatment_id?: string }>();
  const { snap, request } = useData();
  const [tid, setTid] = useState<string | undefined>(params.treatment_id);
  const [date, setDate] = useState<string | undefined>();
  const [time, setTime] = useState<string | undefined>('10:00');
  const [reqId, setReqId] = useState<string | null>(null);
  const p = snap.profile;
  const cat = snap.catalog;
  if (!p || !cat) return null;
  const days = p.reservation.ports.slice(0, -1);
  const sel = cat.spa.find((s) => s.id === tid) ?? cat.spa[0];
  const day = days.find((d) => d.date === date) ?? days.find((d) => d.type === 'port') ?? days[0];
  const price = day.type === 'sea' ? sel.price : Math.round(sel.price * 0.8);

  const submit = async () => {
    const req = await request('book_spa_treatment', { treatment_id: sel.id, date: day.date, time }, `${sel.name} · ${fmtDate(day.date)} ${time}`);
    setReqId(req._id);
  };

  return (
    <ScrollView contentContainerStyle={styles.body}>
      {reqId ? <RequestTracker id={reqId} onRetry={() => setReqId(null)} /> : (
        <>
          <SectionTitle title="Treatment" />
          <ChoiceRow options={cat.spa.map((s) => ({ value: s.id, label: s.name }))} value={sel.id} onChange={setTid} />
          <SectionTitle title="Day" />
          <ChoiceRow options={days.map((d) => ({ value: d.date, label: `${fmtDate(d.date, { weekday: 'short', day: 'numeric' })} · ${d.type === 'sea' ? 'Sea day' : d.port.split(',')[0]}` }))} value={day.date} onChange={setDate} />
          <SectionTitle title="Time" />
          <ChoiceRow options={TIMES.map((t) => ({ value: t, label: t }))} value={time} onChange={setTime} />
          <Card style={{ padding: 16, marginTop: 18, gap: 10 }}>
            <Text style={styles.total}>{money(price)}</Text>
            {day.type !== 'sea' ? <Pill label="Port-day price · 20% off" tone="ok" icon="pricetag" /> : null}
            <Button label="Book treatment" icon="leaf" onPress={() => void submit()} />
          </Card>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  total: { fontSize: 30, fontWeight: '900', color: theme.color.navy, textAlign: 'center' },
});
