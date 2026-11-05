import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useData } from '../data/DataContext';
import { theme } from '../theme';
import { Button, Card, Pill, STATUS_UI } from './components';

/**
 * Live status of one offline-first request, read from the local database:
 * "On device" -> pushed -> processed by the backend through AOM -> synced back.
 */
export function RequestTracker({ id, onRetry, retryLabel = 'Try again' }: { id: string; onRetry?: () => void; retryLabel?: string }) {
  const { snap, sync } = useData();
  const q = snap.requests.find((r) => r._id === id);
  if (!q) return null;
  const ui = STATUS_UI[q.status] ?? STATUS_UI.pending;
  const waiting = q._local || q.status === 'pending' || q.status === 'processing';
  const upgradeAgent = q.agent === 'princess-upgrade-agent' || ['purchase_cabin_upgrade', 'place_upgrade_bid', 'apply_goodwill_upgrade'].includes(q.tool);
  const agentLabel = upgradeAgent ? 'Run by the Stateroom Upgrade agent through Couchbase AOM' : 'Run by the Concierge agent through Couchbase AOM';
  const steps = [
    { label: 'Saved in Couchbase Lite on your phone', done: true },
    { label: sync.status === 'paused' || sync.status === 'offline' ? 'Waiting for a connection…' : 'Synced to Princess Cruises', done: !q._local },
    { label: q.governed === false ? 'Processed by guest services (AOM not configured - ungoverned)' : agentLabel, done: !waiting },
    ...(upgradeAgent && q.governed !== false
      ? [{ label: q.remembered ? `Remembered in AOM Agent Memory${q.memories_recalled ? ` · recalled ${q.memories_recalled} earlier` : ''}` : 'Saving the outcome to AOM Agent Memory', done: !waiting && !!q.remembered }]
      : []),
    { label: q.status === 'awaiting_approval' ? 'Waiting for a Guest Services supervisor' : 'Result synced back to your phone', done: !waiting && q.status !== 'awaiting_approval' },
  ];
  return (
    <Card style={{ padding: 16, gap: 12, marginTop: 16 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={styles.title}>{q.title}</Text>
        <Pill label={q._local ? 'On device' : ui.label} tone={q._local ? 'warn' : ui.tone} icon={ui.icon} />
      </View>
      {steps.map((s, i) => (
        <View key={i} style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          {s.done ? (
            <Ionicons name="checkmark-circle" size={18} color={theme.color.ok} />
          ) : i === steps.findIndex((x) => !x.done) && sync.status !== 'paused' ? (
            <ActivityIndicator size="small" color={theme.color.princess} />
          ) : (
            <Ionicons name="ellipse-outline" size={18} color={theme.color.faint} />
          )}
          <Text style={{ color: s.done ? theme.color.text : theme.color.muted, flex: 1 }}>{s.label}</Text>
        </View>
      ))}
      {q.summary ? <Text style={[styles.summary, q.status === 'failed' && { color: theme.color.danger }]}>{q.summary}</Text> : null}
      {q.governed ? <Text style={styles.tiny}>Governed by Agent Operations Manager{q.trace_id ? ` · trace ${q.trace_id}` : ''}</Text> : null}
      {q.status === 'failed' && onRetry ? <Button label={retryLabel} icon="refresh" onPress={onRetry} /> : null}
      <Button
        label={waiting ? 'Done - it will finish in the background' : 'Done'}
        kind={waiting || (q.status === 'failed' && onRetry) ? 'ghost' : 'gold'}
        onPress={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)'))}
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  title: { fontWeight: '900', color: theme.color.navy, fontSize: theme.type.lg, flex: 1, marginRight: 8 },
  summary: { color: theme.color.text, fontSize: theme.type.md, lineHeight: 21 },
  tiny: { color: theme.color.faint, fontSize: theme.type.xs },
});
