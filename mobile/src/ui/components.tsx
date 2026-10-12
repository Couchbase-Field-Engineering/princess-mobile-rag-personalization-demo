import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { theme, type GradientKey } from '../theme';
import type { RequestStatus, SyncState } from '../types';

export type IconName = React.ComponentProps<typeof Ionicons>['name'];

/** Text wordmark only - no brand artwork ships with this demo. */
export function Wordmark({ light = true, size = 15 }: { light?: boolean; size?: number }) {
  const c = light ? theme.color.onDark : theme.color.navy;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <View style={[styles.mark, { borderColor: theme.color.gold }]}>
        <Ionicons name="boat" size={size * 0.9} color={theme.color.gold} />
      </View>
      <View>
        <Text style={{ color: c, fontSize: size, fontWeight: '800', letterSpacing: 2.2 }}>ROYAL CARIBBEAN</Text>
        <Text style={{ color: light ? theme.color.onDarkMuted : theme.color.muted, fontSize: size * 0.58, letterSpacing: 1.6 }}>
          PERSONALIZATION DEMO
        </Text>
      </View>
    </View>
  );
}

export function Card({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function GradientArt({ palette, icon, height = 96, children }: { palette: string; icon: IconName; height?: number; children?: React.ReactNode }) {
  const colors = (theme.gradient as Record<string, readonly [string, string]>)[palette] ?? theme.gradient.hero;
  return (
    <LinearGradient colors={colors as unknown as [string, string]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={{ height, borderTopLeftRadius: theme.radius, borderTopRightRadius: theme.radius, padding: 14, justifyContent: 'space-between' }}>
      <View style={styles.waves} pointerEvents="none">
        <Ionicons name={icon} size={height * 0.95} color="rgba(255,255,255,0.13)" />
      </View>
      {children}
    </LinearGradient>
  );
}

export function Pill({ label, tone = 'neutral', icon }: { label: string; tone?: 'neutral' | 'gold' | 'ok' | 'warn' | 'danger' | 'ocean' | 'dark'; icon?: IconName }) {
  const map = {
    neutral: [theme.color.bg, theme.color.muted],
    gold: [theme.color.goldSoft, '#7A5A00'],
    ok: [theme.color.okSoft, theme.color.ok],
    warn: [theme.color.warnSoft, theme.color.warn],
    danger: [theme.color.dangerSoft, theme.color.danger],
    ocean: [theme.color.oceanSoft, theme.color.ocean],
    dark: ['rgba(255,255,255,0.16)', theme.color.onDark],
  } as const;
  const [bg, fg] = map[tone];
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      {icon ? <Ionicons name={icon} size={11} color={fg} /> : null}
      <Text style={{ color: fg, fontSize: theme.type.xs, fontWeight: '700' }}>{label}</Text>
    </View>
  );
}

export function Button({ label, onPress, kind = 'gold', icon, disabled, busy, small }: {
  label: string; onPress: () => void; kind?: 'gold' | 'navy' | 'ghost' | 'light'; icon?: IconName; disabled?: boolean; busy?: boolean; small?: boolean;
}) {
  const bg = { gold: theme.color.gold, navy: theme.color.navy, ghost: 'transparent', light: theme.color.surface }[kind];
  const fg = { gold: theme.color.navy, navy: theme.color.onDark, ghost: theme.color.royal, light: theme.color.navy }[kind];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        styles.btn,
        small && styles.btnSmall,
        { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 },
        kind === 'ghost' && { borderWidth: 1, borderColor: theme.color.border },
      ]}
    >
      {busy ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={small ? 14 : 17} color={fg} /> : null}
      <Text style={{ color: fg, fontWeight: '800', fontSize: small ? theme.type.sm : theme.type.md }}>{label}</Text>
    </Pressable>
  );
}

export function SectionTitle({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionText}>{title.toUpperCase()}</Text>
      {action}
    </View>
  );
}

const SYNC_LABEL: Record<SyncState['status'], [string, 'ok' | 'warn' | 'danger' | 'neutral' | 'ocean']> = {
  connecting: ['Connecting', 'ocean'],
  connected: ['Synced', 'ok'],
  idle: ['Synced', 'ok'],
  busy: ['Syncing', 'ocean'],
  offline: ['Offline', 'warn'],
  paused: ['Offline mode', 'warn'],
  error: ['Sync error', 'danger'],
  stopped: ['Local only', 'neutral'],
};

export function SyncBadge({ sync, dark }: { sync: SyncState; dark?: boolean }) {
  const [label, tone] = SYNC_LABEL[sync.status];
  const text = sync.pendingPush ? `${label} · ${sync.pendingPush} to send` : label;
  const dot = { ok: '#3DDC84', warn: theme.color.gold, danger: '#FF6B6B', neutral: theme.color.faint, ocean: '#5CC8FF' }[tone];
  return (
    <View style={[styles.sync, dark ? { backgroundColor: 'rgba(255,255,255,0.12)' } : { backgroundColor: theme.color.bg }]}>
      <View style={[styles.dot, { backgroundColor: dot }]} />
      <Text style={{ color: dark ? theme.color.onDark : theme.color.text, fontSize: theme.type.xs, fontWeight: '700' }}>
        {sync.engine === 'couchbase-lite' ? 'Couchbase Lite · ' : 'Preview · '}
        {text}
      </Text>
    </View>
  );
}

export const STATUS_UI: Record<RequestStatus, { label: string; tone: 'neutral' | 'gold' | 'ok' | 'warn' | 'danger' | 'ocean'; icon: IconName }> = {
  pending: { label: 'Waiting to sync', tone: 'warn', icon: 'cloud-upload-outline' },
  processing: { label: 'Processing', tone: 'ocean', icon: 'sync' },
  awaiting_approval: { label: 'Awaiting supervisor', tone: 'gold', icon: 'shield-checkmark-outline' },
  confirmed: { label: 'Confirmed', tone: 'ok', icon: 'checkmark-circle' },
  accepted: { label: 'Accepted', tone: 'ok', icon: 'checkmark-circle' },
  submitted: { label: 'Bid submitted', tone: 'ocean', icon: 'time-outline' },
  failed: { label: 'Not completed', tone: 'danger', icon: 'alert-circle' },
};

export function Empty({ icon, title, body }: { icon: IconName; title: string; body: string }) {
  return (
    <View style={{ alignItems: 'center', padding: theme.space.xl, gap: 6 }}>
      <Ionicons name={icon} size={34} color={theme.color.faint} />
      <Text style={{ fontWeight: '800', color: theme.color.text, fontSize: theme.type.md }}>{title}</Text>
      <Text style={{ color: theme.color.muted, textAlign: 'center' }}>{body}</Text>
    </View>
  );
}

export const money = (n: number | undefined | null) =>
  n == null ? '' : `$${Number(n).toLocaleString('en-US', { maximumFractionDigits: n % 1 ? 2 : 0 })}`;

export function fmtDate(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric' }) {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', opts);
}

const styles = StyleSheet.create({
  mark: { width: 30, height: 30, borderRadius: 15, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  card: { backgroundColor: theme.color.surface, borderRadius: theme.radius, ...theme.shadow.card },
  waves: { position: 'absolute', right: -6, bottom: -14 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, alignSelf: 'flex-start' },
  btn: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', paddingVertical: 14, paddingHorizontal: 18, borderRadius: 999 },
  btnSmall: { paddingVertical: 8, paddingHorizontal: 14 },
  section: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: theme.space.xl, marginBottom: theme.space.sm },
  sectionText: { color: theme.color.muted, fontSize: theme.type.xs, fontWeight: '800', letterSpacing: 1.4 },
  sync: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, alignSelf: 'flex-start' },
  dot: { width: 7, height: 7, borderRadius: 4 },
});
