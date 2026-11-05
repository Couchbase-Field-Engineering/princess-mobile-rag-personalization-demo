/**
 * Web presentation only: renders the app inside a phone, so the browser demo
 * looks and behaves like the mobile app (393 x 852 points, the size of a
 * current iPhone). On iOS/Android, and in a browser narrower than a phone
 * frame needs (or one opened on an actual phone), it renders the app as is.
 *
 * Inside the frame the app sees real safe-area insets (status bar and home
 * indicator), so every screen lays out exactly as it does on a device. The
 * status bar shows "No service" while Profile → "At sea - no signal" is on.
 *
 * Add ?frame=0 to the URL for the full-width layout.
 */
import { Ionicons } from '@expo/vector-icons';
import { usePathname } from 'expo-router';
import { type ReactNode, useEffect, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaFrameContext, SafeAreaInsetsContext } from 'react-native-safe-area-context';
import { api } from '../api';
import { useData } from '../data/DataContext';
import { theme } from '../theme';

const PHONE_W = 393;
const PHONE_H = 852;
const BEZEL = 12;
const INSETS = { top: 54, bottom: 30, left: 0, right: 0 };
// Screens whose top edge is light, so the status bar text goes dark.
const LIGHT_TOP = ['/cruise', '/profile'];
// Screens whose bottom edge is dark (no tab bar), so the home indicator goes light.
const DARK_BOTTOM = ['/login'];

/** Solid status-bar strip in the colour of the screen's top edge, so content
 * scrolling underneath never collides with the clock. */
function statusBackground(pathname: string, lightTop: boolean): string {
  if (lightTop) return 'rgba(243,245,249,0.97)';
  if (pathname === '/' || pathname === '/login') return theme.gradient.hero[0];
  return theme.color.navy;
}

function frameWanted(): boolean {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return false;
  try {
    return new URLSearchParams(window.location.search).get('frame') !== '0';
  } catch {
    return true;
  }
}

function Clock({ color }: { color: string }) {
  const fmt = () => {
    const d = new Date();
    return `${((d.getHours() + 11) % 12) + 1}:${String(d.getMinutes()).padStart(2, '0')}`;
  };
  const [t, setT] = useState(fmt);
  useEffect(() => {
    const id = setInterval(() => setT(fmt()), 15000);
    return () => clearInterval(id);
  }, []);
  return <Text style={[styles.clock, { color }]}>{t}</Text>;
}

function StatusBarOverlay({ dark, offline, background }: { dark: boolean; offline: boolean; background: string }) {
  const c = dark ? theme.color.text : '#FFFFFF';
  return (
    <View pointerEvents="none" style={[styles.statusBar, { backgroundColor: background }]}>
      <View style={styles.statusSide}><Clock color={c} /></View>
      <View style={styles.island} />
      <View style={[styles.statusSide, { justifyContent: 'flex-end', gap: 6 }]}>
        {offline ? (
          <Text style={[styles.noService, { color: c }]}>No service</Text>
        ) : (
          <>
            <Ionicons name="cellular" size={15} color={c} />
            <Ionicons name="wifi" size={16} color={c} />
          </>
        )}
        <Ionicons name="battery-full" size={22} color={c} />
      </View>
    </View>
  );
}

function SidePanel() {
  const [reset, setReset] = useState<{ busy: boolean; line: string }>({ busy: false, line: '' });
  const resetDemo = async () => {
    if (!window.confirm("Reset the demo? Olivia, Carlos and Priya go back to today's export (requests, stateroom, chat, cached context), their AOM memories are deleted and the concierge's AOM caches are purged.")) return;
    setReset({ busy: true, line: 'Resetting…' });
    try {
      const r = await api<{ summary: { guests: number; requests_removed: number; memories_deleted: number }; export_date: string }>(
        '/api/demo/reset', { method: 'POST', body: {}, timeoutMs: 120000 });
      setReset({ busy: false, line: `Reset done: ${r.summary.guests} guests back to export ${r.export_date}, ${r.summary.requests_removed} requests removed, ${r.summary.memories_deleted} AOM memories deleted. Reloading…` });
      setTimeout(() => window.location.assign('/login'), 1200);
    } catch (e) {
      setReset({ busy: false, line: `Reset failed: ${(e as Error).message}` });
    }
  };
  return (
    <View style={styles.panel}>
      <Text style={styles.kicker}>PRINCESS CRUISES · DEMO</Text>
      <Text style={styles.panelTitle}>Personalized guest app</Text>
      <Text style={styles.panelBody}>
        Every screen renders from the guest's on-device database, synced from Adobe Real-Time CDP's daily guest profile export. The
        concierge is an agent governed by the Couchbase Agent Operations Manager.
      </Text>
      {[
        ['phone-portrait-outline', 'Couchbase Lite', 'Offline-first: bookings queue on the phone while on excursions and sync when online'],
        ['sparkles-outline', 'LLM and Context Caching', 'Answers, and guest context from Adobe Real-Time CDP, cached in Couchbase Agent Operations Manager'],
        ['shield-checkmark-outline', 'Governed agents', 'Confirm runs the Stateroom Upgrade agent, with Couchbase Agent Memory'],
      ].map(([icon, title, body]) => (
        <View key={title} style={styles.point}>
          <Ionicons name={icon as keyof typeof Ionicons.glyphMap} size={18} color={theme.color.accent} />
          <View style={{ flex: 1 }}>
            <Text style={styles.pointTitle}>{title}</Text>
            <Text style={styles.pointBody}>{body}</Text>
          </View>
        </View>
      ))}
      <Pressable onPress={() => window.location.assign('/story')} style={styles.storyBtn}>
        <Ionicons name="book-outline" size={16} color={theme.color.onDark} />
        <Text style={styles.storyText}>The story: Why Couchbase lowers costs</Text>
      </Pressable>
      <Pressable onPress={resetDemo} disabled={reset.busy} style={[styles.resetBtn, reset.busy && { opacity: 0.6 }]}>
        <Ionicons name="refresh-outline" size={16} color={theme.color.princess} />
        <Text style={styles.resetText}>{reset.busy ? 'Resetting…' : 'Reset demo'}</Text>
      </Pressable>
      {reset.line ? <Text style={styles.panelFoot}>{reset.line}</Text> : null}
    </View>
  );
}

export function DeviceFrame({ children }: { children: ReactNode }) {
  const { width, height } = useWindowDimensions();
  const pathname = usePathname();
  const { offline } = useData();
  const [wanted] = useState(frameWanted);
  // A real phone (or a very narrow window) gets the app edge to edge.
  if (!wanted || width < PHONE_W + 2 * BEZEL + 40) return <>{children}</>;

  const outerH = PHONE_H + 2 * BEZEL;
  const scale = Math.min(1, (height - 40) / outerH);
  const showPanel = width >= 980;
  const darkStatus = LIGHT_TOP.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const lightIndicator = DARK_BOTTOM.includes(pathname);

  return (
    <View style={styles.stage}>
      <View style={[styles.row, { gap: showPanel ? 72 : 0 }]}>
        {showPanel ? <SidePanel /> : null}
        <View style={{ width: (PHONE_W + 2 * BEZEL) * scale, height: outerH * scale }}>
          <View style={[styles.phone, { transform: [{ scale }], transformOrigin: 'top left' } as object]}>
            <View style={styles.screen}>
              <SafeAreaFrameContext.Provider value={{ x: 0, y: 0, width: PHONE_W, height: PHONE_H }}>
                <SafeAreaInsetsContext.Provider value={INSETS}>{children}</SafeAreaInsetsContext.Provider>
              </SafeAreaFrameContext.Provider>
              <StatusBarOverlay dark={darkStatus} offline={offline} background={statusBackground(pathname, darkStatus)} />
              <View
                pointerEvents="none"
                style={[styles.homeIndicator, { backgroundColor: lightIndicator ? '#FFFFFF' : theme.color.text }]}
              />
            </View>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stage: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.color.bg,
    backgroundImage: 'radial-gradient(1200px 700px at 30% 20%, #FFFFFF 0%, #E9EDF5 55%, #D8DFEC 100%)',
  } as object,
  row: { flexDirection: 'row', alignItems: 'center' },
  phone: {
    width: PHONE_W + 2 * BEZEL,
    height: PHONE_H + 2 * BEZEL,
    padding: BEZEL,
    borderRadius: 64,
    backgroundColor: '#11131A',
    boxShadow: '0 40px 80px rgba(10,26,63,0.35), 0 0 0 2px #2A2E3A inset',
  } as object,
  screen: { flex: 1, borderRadius: 52, overflow: 'hidden', backgroundColor: theme.color.bg },
  statusBar: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: INSETS.top,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 28,
    zIndex: 10,
  },
  statusSide: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  clock: { fontSize: 16, fontWeight: '700', letterSpacing: 0.2, paddingLeft: 8 },
  noService: { fontSize: 13, fontWeight: '600' },
  island: { width: 122, height: 36, borderRadius: 20, backgroundColor: '#000' },
  homeIndicator: {
    position: 'absolute',
    bottom: 8,
    alignSelf: 'center',
    width: 134,
    height: 5,
    borderRadius: 3,
    opacity: 0.85,
    zIndex: 10,
  },
  panel: { width: 340, gap: 14 },
  kicker: { color: theme.color.princess, fontSize: 12, fontWeight: '800', letterSpacing: 2 },
  panelTitle: { color: theme.color.princess, fontSize: 40, fontWeight: '700', fontFamily: theme.font.display, lineHeight: 46 },
  panelBody: { color: theme.color.muted, fontSize: 15, lineHeight: 22, marginBottom: 6 },
  point: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', backgroundColor: '#FFFFFF', padding: 14, borderRadius: 14, borderWidth: 1, borderColor: theme.color.border },
  pointTitle: { color: theme.color.princess, fontWeight: '800', fontSize: 15 },
  pointBody: { color: theme.color.muted, fontSize: 13, lineHeight: 18, marginTop: 2 },
  storyBtn: { flexDirection: 'row', gap: 8, alignItems: 'center', alignSelf: 'flex-start', backgroundColor: theme.color.accent, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 10, marginTop: 4 },
  storyText: { color: theme.color.onDark, fontWeight: '800', fontSize: 14 },
  resetBtn: { flexDirection: 'row', gap: 8, alignItems: 'center', alignSelf: 'flex-start', backgroundColor: theme.color.surface, borderWidth: 1, borderColor: theme.color.border, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 10 },
  resetText: { color: theme.color.princess, fontWeight: '800', fontSize: 14 },
  panelFoot: { color: theme.color.faint, fontSize: 12, lineHeight: 18, marginTop: 6 },
});
