import { Anchor, Box, Group, Stack, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

export interface BarListRow {
  key: string | number;
  label: string;
  value: number;
  /** Text shown at the end of the row (defaults to the value). */
  display?: ReactNode;
  hint?: ReactNode;
  to?: string;
}

/**
 * Ranked values as labelled bars: one hue, every number written out, so it
 * reads without hovering and works at phone width.
 */
export function BarList({ rows, empty }: { rows: BarListRow[]; empty: ReactNode }) {
  const max = Math.max(...rows.map((r) => r.value), 0);
  if (rows.length === 0 || max <= 0) {
    return (
      <Text size="sm" c="dimmed" py="md" ta="center">
        {empty}
      </Text>
    );
  }
  return (
    <Stack gap={10} role="list">
      {rows.map((row) => (
        <div key={row.key} role="listitem">
          <Group justify="space-between" gap="sm" wrap="nowrap" mb={4}>
            <div style={{ minWidth: 0 }}>
              {row.to ? (
                <Anchor component={Link} to={row.to} size="sm" fw={500} lineClamp={1}>
                  {row.label}
                </Anchor>
              ) : (
                <Text size="sm" fw={500} lineClamp={1}>
                  {row.label}
                </Text>
              )}
              {row.hint && (
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {row.hint}
                </Text>
              )}
            </div>
            <Text size="sm" className="num" fw={500} style={{ whiteSpace: 'nowrap' }}>
              {row.display ?? row.value}
            </Text>
          </Group>
          <Box
            h={6}
            bg="slate.1"
            style={{ borderRadius: 4, overflow: 'hidden' }}
            aria-hidden="true"
          >
            <Box
              h="100%"
              bg="slate.6"
              style={{
                width: `${Math.max((row.value / max) * 100, row.value > 0 ? 2 : 0)}%`,
                borderRadius: 4,
              }}
            />
          </Box>
        </div>
      ))}
    </Stack>
  );
}
