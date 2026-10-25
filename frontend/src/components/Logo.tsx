import { Group, Text } from '@mantine/core';

/**
 * ChhapaKhata brand: a print stamp ("chhapa") over ledger lines ("khata").
 * Drawn on a 312-unit grid; the same artwork is in public/brand/logo-mark.svg
 * and the app icons.
 */
export function LogoMark({ size = 32, onDark = false }: { size?: number; onDark?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 312 312"
      aria-hidden="true"
      focusable="false"
      style={{ flexShrink: 0, display: 'block' }}
    >
      {/* On the dark sidebar a faint edge keeps the tile from melting into it. */}
      <rect
        width="312"
        height="312"
        rx="65"
        fill="#0F172A"
        stroke={onDark ? '#334155' : 'none'}
        strokeWidth={onDark ? 10 : 0}
      />
      <rect x="122" y="43" width="68" height="69" rx="28" fill="#E2E8F0" />
      <rect x="139" y="97" width="34" height="36" fill="#94A3B8" />
      <rect x="73" y="132" width="166" height="44" rx="10" fill="#F8FAFC" />
      <rect x="63" y="205" width="186" height="17" rx="8.5" fill="#94A3B8" />
      <rect x="63" y="239" width="127" height="17" rx="8.5" fill="#94A3B8" />
    </svg>
  );
}

interface LogoProps {
  /** Height of the mark in px; the wordmark scales with it. */
  size?: number;
  /** Light text for dark backgrounds (sidebar, login panel). */
  onDark?: boolean;
  withWordmark?: boolean;
}

export function Logo({ size = 32, onDark = false, withWordmark = true }: LogoProps) {
  return (
    <Group gap={Math.round(size * 0.32)} wrap="nowrap" aria-label="ChhapaKhata" role="img">
      <LogoMark size={size} onDark={onDark} />
      {withWordmark && (
        <Text
          component="span"
          fz={Math.round(size * 0.66)}
          lh={1}
          fw={700}
          style={{ letterSpacing: '-0.02em', whiteSpace: 'nowrap' }}
          c={onDark ? '#F8FAFC' : '#0F172A'}
          aria-hidden="true"
        >
          Chhapa
          <Text span inherit fw={500} c={onDark ? '#94A3B8' : '#64748B'}>
            Khata
          </Text>
        </Text>
      )}
    </Group>
  );
}
