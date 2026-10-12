import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import type { UpgradeOption } from '@/src/types';
import { Button, Card, Empty, Pill, SectionTitle, money } from '@/src/ui/components';
import { RequestTracker } from '@/src/ui/RequestTracker';

export default function Upgrade() {
  const params = useLocalSearchParams<{ category_code?: string; bid?: string }>();
  const { snap, request } = useData();
  const p = snap.profile;
  const offer = snap.offers?.offers.find((o) => o.kind === 'upgrade');
  const options: UpgradeOption[] = offer?.options ?? (snap.contexts.upgrade?.facts?.data?.offers as UpgradeOption[]) ?? [];
  const initial = options.find((o) => o.category_code === params.category_code) ?? options.find((o) => o.recommended) ?? options[0];
  const [code, setCode] = useState(initial?.category_code);
  const sel = options.find((o) => o.category_code === code);
  const [mode, setMode] = useState<'bid' | 'instant'>('bid');
  const [bid, setBid] = useState<number>(Number(params.bid) || sel?.recommended_bid_ppn || sel?.royalup_min_bid_ppn || 50);
  const [reqId, setReqId] = useState<string | null>(null);

  if (!p) return null;
  if (!options.length) return <Empty icon="bed-outline" title="No upgrades available" body="You're in our best available stateroom for this sailing - or upgrade inventory has sold out." />;
  const r = p.reservation;
  const n = r.nights * r.party_size;
  const clampBid = (v: number) => Math.max(sel?.royalup_min_bid_ppn ?? 0, Math.min((sel?.instant_price_ppn ?? v) - 5, v));

  const submit = async () => {
    if (!sel) return;
    const req = mode === 'bid'
      ? await request('place_royalup_bid', { category_code: sel.category_code, bid_per_night_usd: clampBid(bid) }, `RoyalUp bid · ${sel.category_name} · $${clampBid(bid)}/night`)
      : await request('purchase_cabin_upgrade', { category_code: sel.category_code }, `Upgrade to ${sel.category_name}`);
    setReqId(req._id);
  };

  return (
    <ScrollView contentContainerStyle={styles.body}>
      <Card style={{ padding: 16, gap: 4 }}>
        <Text style={styles.meta}>CURRENT STATEROOM</Text>
        <Text style={styles.h2}>{r.stateroom.category_name} · #{r.stateroom.stateroom_number}</Text>
        <Text style={styles.meta}>Deck {r.stateroom.deck} · {r.stateroom.neighborhood} · {r.nights} nights · {r.party_size} guests</Text>
      </Card>

      {reqId ? (
        <RequestTracker id={reqId} onRetry={() => setReqId(null)} />
      ) : (
        <>
          <SectionTitle title="Choose your upgrade" />
          {options.map((o) => (
            <Pressable key={o.category_code} onPress={() => { setCode(o.category_code); setBid(o.recommended_bid_ppn ?? o.royalup_min_bid_ppn); }} disabled={o.available <= 0}>
              <Card style={[styles.opt, code === o.category_code && styles.optSel, o.available <= 0 && { opacity: 0.45 }]}>
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Text style={styles.h3}>{o.category_name}</Text>
                    {o.recommended ? <Pill label="Recommended for you" tone="gold" icon="sparkles" /> : null}
                    <Pill label={o.available > 0 ? `${o.available} left` : 'Sold out'} tone={o.available <= 2 ? 'warn' : 'neutral'} />
                  </View>
                  <Text style={styles.meta}>{o.perks.join(' · ')}</Text>
                  <Text style={styles.meta}>Bid from {money(o.royalup_min_bid_ppn)} · or {money(o.instant_price_ppn)}/person/night instantly</Text>
                </View>
                <Ionicons name={code === o.category_code ? 'radio-button-on' : 'radio-button-off'} size={22} color={theme.color.royal} />
              </Card>
            </Pressable>
          ))}

          {sel ? (
            <>
              <View style={styles.seg}>
                {(['bid', 'instant'] as const).map((m) => (
                  <Pressable key={m} onPress={() => setMode(m)} style={[styles.segBtn, mode === m && styles.segOn]}>
                    <Text style={[styles.segText, mode === m && { color: theme.color.navy }]}>{m === 'bid' ? 'RoyalUp bid' : 'Upgrade now'}</Text>
                  </Pressable>
                ))}
              </View>
              <Card style={{ padding: 16, gap: 10 }}>
                {mode === 'bid' ? (
                  <>
                    <Text style={styles.meta}>Your bid per person, per night. Charged only if accepted.</Text>
                    <View style={styles.stepper}>
                      <Pressable onPress={() => setBid((b) => clampBid(b - 5))} style={styles.step}><Ionicons name="remove" size={22} color={theme.color.navy} /></Pressable>
                      <Text style={styles.bid}>{money(clampBid(bid))}</Text>
                      <Pressable onPress={() => setBid((b) => clampBid(b + 5))} style={styles.step}><Ionicons name="add" size={22} color={theme.color.navy} /></Pressable>
                    </View>
                    <Text style={[styles.meta, { textAlign: 'center' }]}>
                      Total if accepted: {money(clampBid(bid) * n)} · min {money(sel.royalup_min_bid_ppn)}
                      {sel.recommended_bid_ppn ? ` · suggested ${money(sel.recommended_bid_ppn)}` : ''}
                    </Text>
                  </>
                ) : (
                  <>
                    <Text style={styles.meta}>Confirmed instantly, subject to availability.</Text>
                    <Text style={styles.bid}>{money(sel.instant_total_usd)}</Text>
                    <Text style={[styles.meta, { textAlign: 'center' }]}>{money(sel.instant_price_ppn)} × {r.nights} nights × {r.party_size} guests</Text>
                  </>
                )}
                <Button label={mode === 'bid' ? 'Place my bid' : 'Upgrade now'} icon="flash" onPress={() => void submit()} />
                <Text style={styles.tiny}>Works offline: your request is saved in Couchbase Lite and sent when you reconnect.</Text>
              </Card>
            </>
          ) : null}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  h2: { fontSize: theme.type.xl, fontWeight: '900', color: theme.color.navy },
  h3: { fontSize: theme.type.lg, fontWeight: '800', color: theme.color.navy },
  meta: { color: theme.color.muted, fontSize: theme.type.sm },
  tiny: { color: theme.color.faint, fontSize: theme.type.xs, textAlign: 'center' },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, marginBottom: 10, borderWidth: 2, borderColor: 'transparent' },
  optSel: { borderColor: theme.color.gold },
  seg: { flexDirection: 'row', backgroundColor: theme.color.surface, borderRadius: 999, padding: 4, marginVertical: 12, borderWidth: 1, borderColor: theme.color.border },
  segBtn: { flex: 1, paddingVertical: 10, borderRadius: 999, alignItems: 'center' },
  segOn: { backgroundColor: theme.color.gold },
  segText: { fontWeight: '800', color: theme.color.muted },
  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 22 },
  step: { width: 44, height: 44, borderRadius: 22, backgroundColor: theme.color.goldSoft, alignItems: 'center', justifyContent: 'center' },
  bid: { fontSize: 38, fontWeight: '900', color: theme.color.navy, textAlign: 'center' },
});
