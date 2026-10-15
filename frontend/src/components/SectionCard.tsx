import { Card, Group, Text } from '@mantine/core';
import type { ReactNode } from 'react';

interface SectionCardProps {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** Remove inner padding (for edge-to-edge tables). */
  flush?: boolean;
}

export function SectionCard({ title, actions, children, flush }: SectionCardProps) {
  return (
    <Card padding={flush ? 0 : 'lg'}>
      {(title || actions) && (
        <Group
          justify="space-between"
          gap="sm"
          px={flush ? 'lg' : 0}
          pt={flush ? 'md' : 0}
          pb={flush ? 'sm' : 'md'}
          wrap="wrap"
        >
          {typeof title === 'string' ? (
            <Text fw={600} size="md">
              {title}
            </Text>
          ) : (
            title
          )}
          {actions && <Group gap="xs">{actions}</Group>}
        </Group>
      )}
      {children}
    </Card>
  );
}
