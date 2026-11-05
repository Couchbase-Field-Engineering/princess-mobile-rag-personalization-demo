import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import { Button, Card, Empty, fmtDate, GradientArt, Pill, SectionTitle, STATUS_UI, money, type IconName } from '@/src/ui/components';

const ITEM_ICON: Record<string, IconName> = {
  upgrade: 'bed', upgrade_bid: 'trending-up', excursion: 'sunny', dining: 'restaurant', package: 'wine', spa: 'leaf', checkin: 'qr-code',
};

export default function MyCruise() {
  const { snap } = useData();
  const insets = useSafeAreaInsets();
  const p = snap.profile;
  if (!p) return <Empty icon="boat-outline" title="No cruise yet" body="Your reservation syncs from Couchbase in a moment." />;
  const r = p.reservation;
  const items = snap.bookings?.items ?? [];
  const byDate = (d: string) => items.filter((i) => i.date === d);
  const checked = r.checkin_status === 'complete';

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.color.bg }} contentContainerStyle={[styles.body, { paddingTop: insets.top + 12 }]}>
      <Text style={styles.h1}>My Cruise</Text>
      <Text style={styles.sub}>{r.ship_name} · {r.itinerary_name} · Reservation {r.booking_id}</Text>

      <Card style={{ marginTop: 16 }}>
        <GradientArt palette="deck" icon="qr-code" height={110}>
          <Pill label="OceanReady" tone="dark" icon="qr-code-outline" />
          <Text style={styles.passTitle}>{checked ? `Arrival ${r.arrival_slot} · ${fmtDate(r.embark_date)}` : 'Check-in not completed'}</Text>
        </GradientArt>
        <View style={{ padding: 14, gap: 10 }}>
          <Text style={{ color: theme.color.text }}>
            {checked
              ? `Show this at the ${r.embark_port.split(',')[0]} terminal. All ${r.party_size} guests in your party are checked in.`
              : 'Pick a terminal arrival time and confirm your documents. You can do this offline - it sends when you reconnect.'}
          </Text>
          {!checked ? <Button label="Check in now" icon="checkmark-done" onPress={() => router.push('/checkin')} /> : null}
        </View>
      </Card>

      <SectionTitle title="Stateroom" />
      <Card style={{ padding: 16, gap: 4 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text style={styles.room}>{r.stateroom.category_name}</Text>
          <Pill label={`#${r.stateroom.stateroom_number}`} tone="ocean" />
        </View>
        <Text style={styles.meta}>Deck {r.stateroom.deck} · {r.stateroom.neighborhood} · {r.stateroom.location}</Text>
        <Text style={styles.meta}>{r.party.map((m) => m.name.split(' ')[0]).join(', ')}</Text>
        <View style={{ marginTop: 10, alignItems: 'flex-start' }}>
          <Button small kind="ghost" label="Upgrade options" icon="trending-up" onPress={() => router.push('/upgrade')} />
        </View>
      </Card>

      <SectionTitle title="Day by day" />
      {r.ports.map((d) => {
        const its = byDate(d.date);
        const icon: IconName = d.type === 'sea' ? 'water' : d.type === 'port' ? 'location' : 'boat';
        return (
          <View key={d.day} style={styles.day}>
            <View style={styles.dayRail}>
              <View style={styles.dayDot}><Ionicons name={icon} size={14} color={theme.color.onDark} /></View>
              <View style={styles.dayLine} />
            </View>
            <View style={{ flex: 1, paddingBottom: 16 }}>
              <Text style={styles.dayTitle}>Day {d.day} · {d.port.split(',')[0]}</Text>
              <Text style={styles.meta}>
                {fmtDate(d.date)}{d.arrive ? ` · arrive ${d.arrive}` : ''}{d.depart ? ` · depart ${d.depart}` : ''}
              </Text>
              {its.map((i) => (
                <Card key={i.item_id} style={styles.item}>
                  <Ionicons name={ITEM_ICON[i.kind] ?? 'checkmark'} size={18} color={theme.color.princess} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemTitle}>{i.title}</Text>
                    <Text style={styles.meta}>{[i.time, i.charge_usd ? money(i.charge_usd) : null].filter(Boolean).join(' · ')}</Text>
                  </View>
                  <Pill label={i.status === 'submitted' ? 'Bid placed' : 'Booked'} tone={i.status === 'submitted' ? 'ocean' : 'ok'} />
                </Card>
              ))}
            </View>
          </View>
        );
      })}

      <SectionTitle title="All requests" />
      {snap.requests.length === 0 ? (
        <Text style={styles.meta}>Nothing yet - book from For You or ask the Concierge.</Text>
      ) : (
        snap.requests.map((q) => {
          const ui = STATUS_UI[q.status] ?? STATUS_UI.pending;
          return (
            <Card key={q._id} style={[styles.item, { marginLeft: 0 }]}>
              <Ionicons name={ui.icon} size={18} color={theme.color.princess} />
              <View style={{ flex: 1 }}>
                <Text style={styles.itemTitle}>{q.title}</Text>
                {q.summary ? <Text style={styles.meta}>{q.summary}</Text> : null}
                <Text style={styles.tiny}>
                  {q.governed ? 'Governed by Agent Operations Manager' : q._local ? 'Queued in Couchbase Lite' : 'Processed'}
                  {q.trace_id ? ` · trace ${q.trace_id.slice(0, 8)}` : ''}
                </Text>
              </View>
              <Pill label={q._local ? 'On device' : ui.label} tone={q._local ? 'warn' : ui.tone} />
            </Card>
          );
        })
      )}
      <View style={{ height: 30 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' },
  h1: { fontSize: theme.type.title, fontWeight: '700', fontFamily: theme.font.display, color: theme.color.princess },
  sub: { color: theme.color.muted, marginTop: 2 },
  passTitle: { color: theme.color.onDark, fontSize: theme.type.lg, fontWeight: '800' },
  room: { fontSize: theme.type.xl, fontWeight: '900', color: theme.color.navy },
  meta: { color: theme.color.muted, fontSize: theme.type.sm },
  tiny: { color: theme.color.faint, fontSize: theme.type.xs, marginTop: 2 },
  day: { flexDirection: 'row', gap: 12 },
  dayRail: { alignItems: 'center', width: 26 },
  dayDot: { width: 26, height: 26, borderRadius: 13, backgroundColor: theme.color.princess, alignItems: 'center', justifyContent: 'center' },
  dayLine: { flex: 1, width: 2, backgroundColor: theme.color.border },
  dayTitle: { fontWeight: '800', color: theme.color.text, fontSize: theme.type.md, marginTop: 3 },
  item: { flexDirection: 'row', gap: 10, alignItems: 'center', padding: 12, marginTop: 8 },
  itemTitle: { fontWeight: '700', color: theme.color.text },
});
