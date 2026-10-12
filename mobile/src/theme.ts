import { Platform, type ViewStyle } from 'react-native';

/**
 * Royal Caribbean-inspired palette: deep navy and royal blue with a gold
 * accent and ocean blues. Swap in official brand tokens (and the licensed
 * logo/fonts) for a customer-facing build - this demo ships no brand assets.
 */
const shadowCard: ViewStyle = Platform.select({
  ios: { shadowColor: '#0A1A3F', shadowOpacity: 0.12, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } },
  android: { elevation: 3 },
  default: { boxShadow: '0 6px 18px rgba(10,26,63,0.12)' } as ViewStyle,
}) as ViewStyle;

export const theme = {
  color: {
    navy: '#0A1A3F',
    navyDeep: '#06112B',
    royal: '#16357A',
    royalBright: '#1F4BB0',
    gold: '#F5B800',
    goldSoft: '#FFF4D1',
    ocean: '#0077C8',
    oceanSoft: '#E3F2FC',
    bg: '#F3F5F9',
    surface: '#FFFFFF',
    text: '#0B1530',
    muted: '#5D6884',
    faint: '#97A0B6',
    border: '#E2E6EF',
    ok: '#13804B',
    okSoft: '#E6F6EE',
    warn: '#B26200',
    warnSoft: '#FFF3E0',
    danger: '#C0262D',
    dangerSoft: '#FDECEC',
    onDark: '#FFFFFF',
    onDarkMuted: 'rgba(255,255,255,0.72)',
  },
  gradient: {
    hero: ['#06112B', '#16357A'] as const,
    suite: ['#16357A', '#6A3FB5'] as const,
    ocean: ['#0077C8', '#00B3B0'] as const,
    dining: ['#5B1A2E', '#B6463C'] as const,
    drinks: ['#B6463C', '#F5B800'] as const,
    spa: ['#2E6B62', '#8CC7B1'] as const,
    deck: ['#0A1A3F', '#0077C8'] as const,
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  type: { xs: 11, sm: 13, md: 15, lg: 17, xl: 20, title: 26, hero: 34 },
  radius: 18,
  radiusSm: 10,
  shadow: { card: shadowCard },
} as const;

export type GradientKey = keyof typeof theme.gradient;
