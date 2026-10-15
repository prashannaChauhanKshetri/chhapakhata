import { Center, Stack, Text, ThemeIcon } from '@mantine/core';
import { IconInbox } from '@tabler/icons-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ title, description, icon, action, compact }: EmptyStateProps) {
  return (
    <Center py={compact ? 'lg' : 48}>
      <Stack align="center" gap={6} maw={360} ta="center">
        <ThemeIcon variant="light" color="slate" size={compact ? 36 : 44} radius="xl">
          {icon ?? <IconInbox size={compact ? 18 : 22} stroke={1.6} />}
        </ThemeIcon>
        <Text fw={600}>{title}</Text>
        {description && (
          <Text size="sm" c="dimmed">
            {description}
          </Text>
        )}
        {action && <div style={{ marginTop: 6 }}>{action}</div>}
      </Stack>
    </Center>
  );
}
