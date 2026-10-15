import { Badge, type BadgeProps, Box, Group, Text } from '@mantine/core';

import { STAGES, type StatusStyle } from '@/lib/status';

interface StatusBadgeProps extends Omit<BadgeProps, 'color'> {
  value: string;
  map: Record<string, StatusStyle>;
  label?: string;
}

export function StatusBadge({ value, map, label, ...props }: StatusBadgeProps) {
  const style = map[value] ?? { label: label ?? value, color: 'slate' };
  return (
    <Badge color={style.color} {...props}>
      {label ?? style.label}
    </Badge>
  );
}

/** Production stage: a coloured dot and a short label. Quiet by design. */
export function StageBadge({ stage, full = false }: { stage: number; full?: boolean }) {
  const style = STAGES[stage] ?? STAGES[1];
  return (
    <Group gap={6} wrap="nowrap">
      <Box
        w={8}
        h={8}
        style={{ borderRadius: 999, flex: 'none' }}
        bg={style.color === 'slate' ? 'slate.4' : `${style.color}.6`}
      />
      <Text size="sm" c="slate.7" lineClamp={1}>
        {full ? style.label : style.short}
      </Text>
    </Group>
  );
}
