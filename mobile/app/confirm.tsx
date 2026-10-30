import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';
import { useData } from '@/src/data/DataContext';
import { theme } from '@/src/theme';
import { Button, Card, Pill } from '@/src/ui/components';
import { RequestTracker } from '@/src/ui/RequestTracker';

const TOOL_LABEL: Record<string, string> = {
  book_shore_excursion: 'Book shore excursion',
  purchase_package: 'Add package to your cruise',
  place_upgrade_bid: 'Place Princess Upgrade bid',
  purchase_cabin_upgrade: 'Upgrade stateroom',
  apply_goodwill_upgrade: 'Request a complimentary upgrade',
};

/** One-tap actions from For You and the Concierge land here before they're queued. */
export default function Confirm() {
  const { tool = '', args = '{}', title = '', price = '' } = useLocalSearchParams<{ tool: string; args: string; title: string; price: string }>();
  const { request } = useData();
  const [reqId, setReqId] = useState<string | null>(null);
  const parsed = JSON.parse(args) as Record<string, unknown>;

  const submit = async () => {
    const req = await request(tool, parsed, title || TOOL_LABEL[tool] || tool);
    setReqId(req._id);
  };

  return (
    <ScrollView contentContainerStyle={styles.body}>
      {reqId ? <RequestTracker id={reqId} onRetry={() => setReqId(null)} /> : (
        <Card style={{ padding: 18, gap: 12 }}>
          <Pill label={TOOL_LABEL[tool] ?? tool} tone="ocean" />
          <Text style={styles.h2}>{title}</Text>
          {price ? <Text style={styles.price}>{price}</Text> : null}
          {tool === 'apply_goodwill_upgrade' ? (
            <Text style={styles.meta}>Complimentary upgrades are reviewed by a Guest Services supervisor before they're applied. You'll see their decision here.</Text>
          ) : (
            <Text style={styles.meta}>Charged to the card on your reservation. Your request is saved on this phone and sent as soon as you're connected.</Text>
          )}
          <Button label="Confirm" icon="checkmark" onPress={() => void submit()} />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' },
  h2: { fontSize: theme.type.xl, fontWeight: '900', color: theme.color.navy },
  price: { fontSize: theme.type.lg, fontWeight: '800', color: theme.color.princess },
  meta: { color: theme.color.muted, fontSize: theme.type.sm, lineHeight: 19 },
});
