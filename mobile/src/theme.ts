import { Platform, type ViewStyle } from 'react-native';

/**
 * Styled after princess.com (Nov 2026): ink text (#020215) on white and warm
 * off-whites (#F6F4F2), Princess blue (#003595) for headings, links and the
 * hero, magenta (#E60060) pill buttons for the primary call to action, pale
 * aqua (#CCE7EB) panels, and a serif display face for headlines next to a
 * clean sans for everything else. The site's own faces (Domaine Display,
 * Proxima Nova) are licensed, so the demo uses the platform serif / sans in
 * their place; drop the licensed fonts and logo in for a customer-facing build.
 * `gold` is kept for Captain's Circle loyalty pills only.
 */
const shadowCard: ViewStyle = Platform.select({
  ios: { shadowColor: '#00235F', shadowOpacity: 0.12, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } },
  android: { elevation: 3 },
  default: { boxShadow: '0 6px 18px rgba(0,35,95,0.12)' } as ViewStyle,
}) as ViewStyle;

export const theme = {
  color: {
    navy: '#00235F',          // deep Princess blue (dark surfaces, hero)
    navyDeep: '#001640',
    princess: '#003595',      // princess.com brand blue: headings, links, nav
    princessBright: '#1A56C4',
    accent: '#E60060',        // princess.com call-to-action magenta
    accentSoft: '#FDE4EE',
    gold: '#C9A227',          // Captain's Circle only
    goldSoft: '#FAF1DA',
    ocean: '#0E7490',
    oceanSoft: '#CCE7EB',     // princess.com pale aqua panels
    bg: '#F6F4F2',            // princess.com warm off-white
    surface: '#FFFFFF',
    text: '#020215',          // princess.com ink
    muted: '#5B5B6B',
    faint: '#9A9AA6',
    border: '#D3D3D7',
    ok: '#13804B',
    okSoft: '#E6F6EE',
    warn: '#B26200',
    warnSoft: '#FFF3E0',
    danger: '#C0262D',
    dangerSoft: '#FDECEC',
    onDark: '#FFFFFF',
    onDarkMuted: 'rgba(255,255,255,0.74)',
  },
  gradient: {
    hero: ['#001640', '#003595'] as const,
    suite: ['#003595', '#5B2E91'] as const,
    ocean: ['#1C86D1', '#2BB3A3'] as const,
    dining: ['#5B1A2E', '#B6463C'] as const,
    drinks: ['#B6463C', '#E60060'] as const,
    spa: ['#2E6B62', '#8CC7B1'] as const,
    deck: ['#00235F', '#0E7490'] as const,
  },
  // Serif display face for headlines (princess.com uses Domaine Display); the
  // platform serif stands in. Body text stays on the system sans.
  font: {
    display: Platform.select({ ios: 'Georgia', android: 'serif', default: "Georgia, 'Times New Roman', serif" }) as string,
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  type: { xs: 11, sm: 13, md: 15, lg: 17, xl: 20, title: 26, hero: 34 },
  radius: 18,
  radiusSm: 10,
  shadow: { card: shadowCard },
} as const;

export type GradientKey = keyof typeof theme.gradient;
