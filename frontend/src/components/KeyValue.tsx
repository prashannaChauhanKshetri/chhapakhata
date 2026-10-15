import { Group, Stack, Text } from '@mantine/core';
import type { ReactNode } from 'react';

export interface KeyValueItem {
  label: string;
  value: ReactNode;
  hidden?: boolean;
}

/** Label/value pairs, e.g. on detail pages. */
export function KeyValue({
  items,
  labelWidth = 140,
}: {
  items: KeyValueItem[];
  labelWidth?: number;
}) {
  return (
    <Stack gap={8}>
      {items
        .filter((item) => !item.hidden)
        .map((item) => (
          <Group key={item.label} gap="md" wrap="nowrap" align="flex-start">
            <Text size="sm" c="dimmed" w={labelWidth} style={{ flex: 'none' }}>
              {item.label}
            </Text>
            <Text size="sm" component="div" style={{ minWidth: 0, flex: 1 }}>
              {item.value ?? '—'}
            </Text>
          </Group>
        ))}
    </Stack>
  );
}
