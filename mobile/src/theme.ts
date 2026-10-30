import { Platform, type ViewStyle } from 'react-native';

/**
 * Princess Cruises-inspired palette: deep navy and Princess blue with a
 * champagne-gold accent and sea blues. Swap in official brand tokens (and the licensed
 * logo/fonts) for a customer-facing build - this demo ships no brand assets.
 */
const shadowCard: ViewStyle = Platform.select({
  ios: { shadowColor: '#0B2545', shadowOpacity: 0.12, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } },
  android: { elevation: 3 },
  default: { boxShadow: '0 6px 18px rgba(11,37,69,0.12)' } as ViewStyle,
}) as ViewStyle;

export const theme = {
  color: {
    navy: '#0B2545',
    navyDeep: '#061A33',
    princess: '#1B4F9C',
    princessBright: '#2A6BC9',
    gold: '#D9AE4F',
    goldSoft: '#FAF1DA',
    ocean: '#1C86D1',
    oceanSoft: '#E4F1FB',
    bg: '#F3F5F9',
    surface: '#FFFFFF',
    text: '#0A1A30',
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
    hero: ['#061A33', '#1B4F9C'] as const,
    suite: ['#1B4F9C', '#5B4FA8'] as const,
    ocean: ['#1C86D1', '#2BB3A3'] as const,
    dining: ['#5B1A2E', '#B6463C'] as const,
    drinks: ['#B6463C', '#D9AE4F'] as const,
    spa: ['#2E6B62', '#8CC7B1'] as const,
    deck: ['#0B2545', '#1C86D1'] as const,
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  type: { xs: 11, sm: 13, md: 15, lg: 17, xl: 20, title: 26, hero: 34 },
  radius: 18,
  radiusSm: 10,
  shadow: { card: shadowCard },
} as const;

export type GradientKey = keyof typeof theme.gradient;
