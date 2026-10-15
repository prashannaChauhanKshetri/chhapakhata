import { Anchor, Group, Stack, Text, Title } from '@mantine/core';
import { IconChevronLeft } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Buttons shown on the right (wrap below the title on small screens). */
  actions?: ReactNode;
  back?: { to: string; label: string };
  badge?: ReactNode;
}

export function PageHeader({ title, description, actions, back, badge }: PageHeaderProps) {
  return (
    <Stack gap={6} mb="lg">
      {back && (
        <Anchor component={Link} to={back.to} size="sm" c="dimmed" w="fit-content">
          <Group gap={2}>
            <IconChevronLeft size={16} />
            {back.label}
          </Group>
        </Anchor>
      )}
      <Group justify="space-between" align="flex-start" gap="md" wrap="wrap">
        <Stack gap={4} miw={0} style={{ flex: '1 1 320px' }}>
          <Group gap="sm" wrap="nowrap">
            <Title order={1} lineClamp={1}>
              {title}
            </Title>
            {badge}
          </Group>
          {description && (
            <Text c="dimmed" size="sm">
              {description}
            </Text>
          )}
        </Stack>
        {actions && (
          <Group gap="xs" wrap="wrap">
            {actions}
          </Group>
        )}
      </Group>
    </Stack>
  );
}
