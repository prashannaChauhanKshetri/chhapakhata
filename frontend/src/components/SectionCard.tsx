import { Card, Group, Text } from '@mantine/core';
import type { ReactNode } from 'react';

interface SectionCardProps {
  title?: ReactNode;
  /** One or two lines under the title explaining the section. */
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** Remove inner padding (for edge-to-edge tables). */
  flush?: boolean;
}

export function SectionCard({ title, description, actions, children, flush }: SectionCardProps) {
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
          <div>
            {typeof title === 'string' ? (
              <Text fw={600} size="md">
                {title}
              </Text>
            ) : (
              title
            )}
            {description && (
              <Text size="sm" c="dimmed" mt={2} maw={760}>
                {description}
              </Text>
            )}
          </div>
          {actions && <Group gap="xs">{actions}</Group>}
        </Group>
      )}
      {children}
    </Card>
  );
}
