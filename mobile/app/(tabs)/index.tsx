import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import type { Offer } from '@/src/types';
import { Card, Empty, fmtDate, GradientArt, Pill, SectionTitle, STATUS_UI, SyncBadge, Wordmark } from '@/src/ui/components';
import { KIND_ICON, KIND_LABEL, openAction } from '@/src/ui/offerNav';

function daysTo(iso: string, today: string) {
  const [a, b] = [new Date(iso.slice(0, 10)), new Date(today.slice(0, 10))];
  return Math.round((a.getTime() - b.getTime()) / 86400000);
}

export default function ForYou() {
  const { snap, sync, refresh } = useData();
  const insets = useSafeAreaInsets();
  const p = snap.profile;
  const r = p?.reservation;
  const today = p?.export_date ?? new Date().toISOString();
  const offers = snap.offers?.offers ?? [];
  const recent = snap.requests.slice(0, 3);
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.color.bg }} refreshControl={<RefreshControl refreshing={false} onRefresh={() => void refresh()} />}>
      <LinearGradient colors={theme.gradient.hero as unknown as [string, string]} style={[styles.hero, { paddingTop: insets.top + 14 }]}>
        <View style={styles.row}>
          <Wordmark size={12} />
          <SyncBadge sync={sync} dark />
        </View>
        {p && r ? (
          <>
            <Text style={styles.greet}>{greet}, {p.first_name}</Text>
            <View style={styles.countRow}>
              <View>
                <Text style={styles.countNum}>{Math.max(0, daysTo(r.embark_date, today))}</Text>
                <Text style={styles.countLbl}>DAYS TO SAIL</Text>
              </View>
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={styles.ship}>{r.ship_name}</Text>
                <Text style={styles.itin}>{r.itinerary_name}</Text>
                <Text style={styles.itin}>{fmtDate(r.embark_date)} from {r.embark_port.split(',')[0]}</Text>
              </View>
            </View>
            <View style={[styles.row, { marginTop: 14, justifyContent: 'flex-start', gap: 8, flexWrap: 'wrap' }]}>
              <Pill label={`${p.loyalty.tier} · Captain's Circle`} tone="gold" icon="star" />
              <Pill label={`${r.stateroom.category_name} ${r.stateroom.stateroom_number}`} tone="dark" icon="bed-outline" />
              <Pill label={`Party of ${r.party_size}`} tone="dark" icon="people-outline" />
            </View>
          </>
        ) : (
          <Text style={[styles.greet, { marginTop: 24 }]}>Loading your cruise from Couchbase Lite…</Text>
        )}
      </LinearGradient>

      <View style={styles.body}>
        {recent.length ? (
          <>
            <SectionTitle title="Your requests" />
            <Card style={{ padding: 4 }}>
              {recent.map((q, i) => {
                const ui = STATUS_UI[q.status] ?? STATUS_UI.pending;
                return (
                  <View key={q._id} style={[styles.req, i > 0 && styles.reqBorder]}>
                    <Ionicons name={ui.icon} size={20} color={theme.color.princess} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.reqTitle}>{q.title}</Text>
                      <Text style={styles.reqSub} numberOfLines={2}>
                        {q.summary ?? (q._local || q.status === 'pending' ? 'Saved on your phone - sends automatically when you have a connection.' : '')}
                      </Text>
                    </View>
                    <Pill label={q._local ? 'On device' : ui.label} tone={q._local ? 'warn' : ui.tone} />
                  </View>
                );
              })}
            </Card>
          </>
        ) : null}

        <SectionTitle
          title="Picked for you"
          action={snap.offers ? <Text style={styles.prov}>{snap.offers.segment}</Text> : null}
        />
        {offers.length === 0 ? (
          <Empty icon="sparkles-outline" title="Personalizing…" body="Your offers sync from Couchbase in a moment." />
        ) : (
          offers.map((o) => <OfferCard key={o.offer_id} o={o} />)
        )}
        {snap.offers ? (
          <Text style={styles.footnote}>
            Ranked by {snap.offers.model_version} on Databricks (export {snap.offers.export_date}) and re-ranked live after every booking.
            Stored on this phone in Couchbase Lite.
          </Text>
        ) : null}
      </View>
    </ScrollView>
  );
}

function OfferCard({ o }: { o: Offer }) {
  return (
    <Pressable onPress={() => openAction(o.cta, o.title, o.price_label)} style={({ pressed }) => [{ marginBottom: 14, opacity: pressed ? 0.92 : 1 }]}>
      <Card>
        <GradientArt palette={o.palette} icon={KIND_ICON[o.kind] ?? 'sparkles'} height={o.rank === 1 ? 118 : 92}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Pill label={KIND_LABEL[o.kind] ?? o.kind} tone="dark" icon={KIND_ICON[o.kind]} />
            {o.rank <= 2 ? <Pill label={o.rank === 1 ? 'Top pick' : 'For you'} tone="accent" icon="sparkles" /> : null}
          </View>
          <Text style={styles.offerTitle} numberOfLines={2}>{o.title}</Text>
        </GradientArt>
        <View style={{ padding: 14, gap: 6 }}>
          <Text style={styles.offerSub}>{o.subtitle}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="sparkles" size={13} color={theme.color.ocean} />
            <Text style={styles.reason}>{o.reason}</Text>
          </View>
          <View style={[styles.row, { marginTop: 6 }]}>
            <Text style={styles.price}>{o.price_label}</Text>
            <View style={styles.cta}>
              <Text style={styles.ctaText}>{o.cta.label}</Text>
              <Ionicons name="arrow-forward" size={15} color={theme.color.navy} />
            </View>
          </View>
        </View>
      </Card>
    </Pressable>
  );
}



const styles = StyleSheet.create({
  hero: { paddingHorizontal: 20, paddingBottom: 26, borderBottomLeftRadius: 28, borderBottomRightRadius: 28 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  greet: { color: theme.color.onDark, fontSize: theme.type.title, fontWeight: '700', fontFamily: theme.font.display, marginTop: 22 },
  countRow: { flexDirection: 'row', gap: 18, marginTop: 14, alignItems: 'center' },
  countNum: { color: theme.color.onDark, fontSize: 52, fontWeight: '700', fontFamily: theme.font.display, lineHeight: 56 },
  countLbl: { color: theme.color.onDarkMuted, fontSize: theme.type.xs, fontWeight: '800', letterSpacing: 1.4 },
  ship: { color: theme.color.onDark, fontSize: theme.type.xl, fontWeight: '700', fontFamily: theme.font.display },
  itin: { color: theme.color.onDarkMuted, fontSize: theme.type.sm },
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' },
  req: { flexDirection: 'row', gap: 10, alignItems: 'center', padding: 12 },
  reqBorder: { borderTopWidth: 1, borderTopColor: theme.color.border },
  reqTitle: { fontWeight: '800', color: theme.color.text },
  reqSub: { color: theme.color.muted, fontSize: theme.type.sm },
  prov: { color: theme.color.princess, fontSize: theme.type.xs, fontWeight: '700' },
  offerTitle: { color: theme.color.onDark, fontSize: theme.type.xl, fontWeight: '900' },
  offerSub: { color: theme.color.text, fontSize: theme.type.md },
  reason: { color: theme.color.ocean, fontSize: theme.type.sm, fontWeight: '700', flex: 1 },
  price: { color: theme.color.text, fontWeight: '800' },
  cta: { flexDirection: 'row', gap: 6, alignItems: 'center', backgroundColor: theme.color.accent, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
  ctaText: { color: theme.color.onDark, fontWeight: '800', fontSize: theme.type.sm },
  footnote: { color: theme.color.faint, fontSize: theme.type.xs, textAlign: 'center', marginVertical: 18, lineHeight: 16 },
});
