import { Card, Group, type MantineColor, Skeleton, Stack, Text, ThemeIcon } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  to?: string;
  loading?: boolean;
  /** Draws attention (e.g. overdue jobs) with a coloured value. */
  tone?: 'default' | 'warning' | 'danger';
  /** Icon tint, so each kind of figure is recognisable at a glance. */
  accent?: MantineColor;
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  to,
  loading,
  tone = 'default',
  accent = 'slate',
}: StatCardProps) {
  const color = tone === 'danger' ? 'red.7' : tone === 'warning' ? 'amber.8' : 'slate.9';
  const card = (
    <Card padding="md" h="100%" style={to ? { cursor: 'pointer' } : undefined}>
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
        <Stack gap={4} miw={0}>
          <Text size="sm" c="dimmed" fw={500}>
            {label}
          </Text>
          {loading ? (
            <Skeleton h={30} w={120} />
          ) : (
            <Text fz={{ base: 22, sm: 28 }} fw={600} lh={1.15} c={color} className="num">
              {value}
            </Text>
          )}
          {hint && (
            <Text size="xs" c="dimmed">
              {hint}
            </Text>
          )}
        </Stack>
        {icon && (
          <ThemeIcon variant="light" color={accent} size={36} radius="md">
            {icon}
          </ThemeIcon>
        )}
      </Group>
    </Card>
  );
  return to ? (
    <Link to={to} style={{ textDecoration: 'none', color: 'inherit' }}>
      {card}
    </Link>
  ) : (
    card
  );
}
