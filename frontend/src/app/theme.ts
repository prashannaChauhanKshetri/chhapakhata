/**
 * Design system: the neutral slate palette from the client's reference
 * (#F8FAFC · #E2E8F0 · #94A3B8 · #334155 · #0F172A) with in-between shades from
 * the same slate family. Primary actions use #334155. Colour beyond slate is
 * reserved for meaning: status badges, alerts, overdue and low-stock signals.
 *
 * Contrast notes (on white): #0F172A 17.9:1, #334155 10.4:1, #475569 7.6:1,
 * #64748B 4.8:1 (smallest allowed for text). #94A3B8 is 2.6:1, so it is used
 * only for borders, icons, placeholders and disabled states, never body text.
 */
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  createTheme,
  type MantineColorsTuple,
  Modal,
  NumberInput,
  Paper,
  rem,
  Select,
  Table,
  Textarea,
  TextInput,
  Tooltip,
} from '@mantine/core';

export const palette = {
  bg: '#F8FAFC',
  surface: '#FFFFFF',
  border: '#E2E8F0',
  decor: '#94A3B8',
  textMuted: '#64748B',
  textStrong: '#334155',
  text: '#0F172A',
  sidebar: '#0F172A',
} as const;

const slate: MantineColorsTuple = [
  '#F8FAFC',
  '#F1F5F9',
  '#E2E8F0',
  '#CBD5E1',
  '#94A3B8',
  '#64748B',
  '#475569',
  '#334155',
  '#1E293B',
  '#0F172A',
];

// Semantic palettes (Tailwind scales, the same family as slate) for status only.
const green: MantineColorsTuple = [
  '#F0FDF4',
  '#DCFCE7',
  '#BBF7D0',
  '#86EFAC',
  '#4ADE80',
  '#22C55E',
  '#16A34A',
  '#15803D',
  '#166534',
  '#14532D',
];
const amber: MantineColorsTuple = [
  '#FFFBEB',
  '#FEF3C7',
  '#FDE68A',
  '#FCD34D',
  '#FBBF24',
  '#F59E0B',
  '#D97706',
  '#B45309',
  '#92400E',
  '#78350F',
];
const red: MantineColorsTuple = [
  '#FEF2F2',
  '#FEE2E2',
  '#FECACA',
  '#FCA5A5',
  '#F87171',
  '#EF4444',
  '#DC2626',
  '#B91C1C',
  '#991B1B',
  '#7F1D1D',
];
const blue: MantineColorsTuple = [
  '#EFF6FF',
  '#DBEAFE',
  '#BFDBFE',
  '#93C5FD',
  '#60A5FA',
  '#3B82F6',
  '#2563EB',
  '#1D4ED8',
  '#1E40AF',
  '#1E3A8A',
];
const violet: MantineColorsTuple = [
  '#F5F3FF',
  '#EDE9FE',
  '#DDD6FE',
  '#C4B5FD',
  '#A78BFA',
  '#8B5CF6',
  '#7C3AED',
  '#6D28D9',
  '#5B21B6',
  '#4C1D95',
];

const fontFamily =
  "'Inter Variable', Inter, 'Noto Sans Devanagari', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

export const theme = createTheme({
  primaryColor: 'slate',
  primaryShade: 7,
  colors: { slate, gray: slate, green, amber, yellow: amber, red, blue, violet },
  white: '#FFFFFF',
  black: palette.text,
  fontFamily,
  fontFamilyMonospace: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace",
  fontSizes: {
    xs: rem(12),
    sm: rem(14),
    md: rem(16),
    lg: rem(18),
    xl: rem(20),
  },
  lineHeights: { xs: '1.4', sm: '1.5', md: '1.5', lg: '1.45', xl: '1.4' },
  fontWeights: { regular: '400', medium: '500', bold: '600' },
  headings: {
    fontFamily,
    fontWeight: '600',
    sizes: {
      h1: { fontSize: rem(24), lineHeight: '1.25' },
      h2: { fontSize: rem(20), lineHeight: '1.3' },
      h3: { fontSize: rem(18), lineHeight: '1.35' },
      h4: { fontSize: rem(16), lineHeight: '1.4' },
      h5: { fontSize: rem(14), lineHeight: '1.4' },
    },
  },
  spacing: { xs: rem(8), sm: rem(12), md: rem(16), lg: rem(24), xl: rem(32) },
  radius: { xs: rem(4), sm: rem(6), md: rem(8), lg: rem(12), xl: rem(16) },
  defaultRadius: 'md',
  shadows: {
    xs: '0 1px 2px rgba(15, 23, 42, 0.05)',
    sm: '0 1px 3px rgba(15, 23, 42, 0.08)',
    md: '0 4px 12px rgba(15, 23, 42, 0.08)',
    lg: '0 8px 24px rgba(15, 23, 42, 0.10)',
    xl: '0 16px 40px rgba(15, 23, 42, 0.12)',
  },
  breakpoints: { xs: '36em', sm: '48em', md: '62em', lg: '75em', xl: '88em' },
  cursorType: 'pointer',
  focusRing: 'auto',
  components: {
    Button: Button.extend({ defaultProps: { size: 'sm', fw: 500 } }),
    ActionIcon: ActionIcon.extend({ defaultProps: { variant: 'subtle', color: 'slate' } }),
    TextInput: TextInput.extend({ defaultProps: { size: 'sm' } }),
    NumberInput: NumberInput.extend({ defaultProps: { size: 'sm', hideControls: true } }),
    Select: Select.extend({
      defaultProps: { size: 'sm', allowDeselect: false, checkIconPosition: 'right' },
    }),
    Textarea: Textarea.extend({ defaultProps: { size: 'sm', autosize: true, minRows: 2 } }),
    Card: Card.extend({
      defaultProps: { withBorder: true, radius: 'lg', padding: 'lg', shadow: 'none' },
    }),
    Paper: Paper.extend({ defaultProps: { radius: 'lg' } }),
    Badge: Badge.extend({
      defaultProps: { radius: 'sm', variant: 'light', size: 'md', fw: 500 },
      styles: { root: { textTransform: 'none', letterSpacing: 0 } },
    }),
    Modal: Modal.extend({
      defaultProps: {
        radius: 'lg',
        centered: true,
        overlayProps: { backgroundOpacity: 0.4, blur: 1 },
      },
    }),
    Table: Table.extend({ defaultProps: { verticalSpacing: 'sm', horizontalSpacing: 'md' } }),
    Tooltip: Tooltip.extend({
      defaultProps: { withArrow: true, openDelay: 300, color: 'slate.9' },
    }),
  },
});
