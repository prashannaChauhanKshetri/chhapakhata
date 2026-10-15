import { Stack, Text } from '@mantine/core';

import { formatDate } from '@/lib/format';

interface DualDateProps {
  ad: string | null | undefined;
  bs?: string | null;
  /** Put both on one line instead of stacking. */
  inline?: boolean;
}

/** A date in both calendars: BS (Miti) first, as staff read it, AD below. */
export function DualDate({ ad, bs, inline = false }: DualDateProps) {
  if (!ad)
    return (
      <Text span c="dimmed">
        —
      </Text>
    );
  if (inline) {
    return (
      <Text span size="sm">
        {bs ? `${bs} BS · ` : ''}
        <Text span c="dimmed" size="sm">
          {formatDate(ad)}
        </Text>
      </Text>
    );
  }
  return (
    <Stack gap={0}>
      <Text size="sm">{bs ? `${bs} BS` : formatDate(ad)}</Text>
      {bs && (
        <Text size="xs" c="dimmed">
          {formatDate(ad)}
        </Text>
      )}
    </Stack>
  );
}
