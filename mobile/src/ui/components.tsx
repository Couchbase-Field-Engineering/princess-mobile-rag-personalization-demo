import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { theme, type GradientKey } from '../theme';
import type { RequestStatus, SyncState } from '../types';

export type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * Wordmark in the style of the Princess live-chat header: the brand mark on the
 * left, the uppercase wordmark beside it. The mark is `assets/images/brand-logo.png`,
 * which ships as a generic placeholder - drop the licensed Princess mark in at
 * that path (same name, square PNG with transparent background) for a
 * customer-facing build. No licensed artwork is included in this repo.
 */
const BRAND_MARK = require('../../assets/images/brand-logo.png');

export function Wordmark({ light = true, size = 15 }: { light?: boolean; size?: number }) {
  const c = light ? theme.color.onDark : theme.color.navy;
  const mark = size * 2.1;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <Image source={BRAND_MARK} style={{ width: mark, height: mark, borderRadius: mark * 0.24 }} resizeMode="contain" accessibilityLabel="Princess Cruises" />
      <View>
        <Text style={{ color: c, fontSize: size, fontWeight: '800', letterSpacing: 2.2 }}>PRINCESS CRUISES</Text>
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

export function Pill({ label, tone = 'neutral', icon }: { label: string; tone?: 'neutral' | 'gold' | 'accent' | 'ok' | 'warn' | 'danger' | 'ocean' | 'dark'; icon?: IconName }) {
  const map = {
    neutral: [theme.color.bg, theme.color.muted],
    gold: [theme.color.goldSoft, '#7A5A00'],
    accent: [theme.color.accentSoft, theme.color.accent],
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
  // princess.com's primary call to action: a magenta pill with white text.
  const bg = { gold: theme.color.accent, navy: theme.color.princess, ghost: 'transparent', light: theme.color.surface }[kind];
  const fg = { gold: theme.color.onDark, navy: theme.color.onDark, ghost: theme.color.princess, light: theme.color.princess }[kind];
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
  const dot = { ok: '#3DDC84', warn: '#F5B800', danger: '#FF6B6B', neutral: theme.color.faint, ocean: '#5CC8FF' }[tone];
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

export const STATUS_UI: Record<RequestStatus, { label: string; tone: 'neutral' | 'gold' | 'accent' | 'ok' | 'warn' | 'danger' | 'ocean'; icon: IconName }> = {
  pending: { label: 'Waiting to sync', tone: 'warn', icon: 'cloud-upload-outline' },
  processing: { label: 'Processing', tone: 'ocean', icon: 'sync' },
  awaiting_approval: { label: 'Awaiting supervisor', tone: 'warn', icon: 'shield-checkmark-outline' },
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
