import { Button, Center, Stack, Text, Title } from '@mantine/core';
import { IconLock } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import type { PermName } from '@/lib/permissions';

import { useAuth } from './AuthContext';

/** Route guard: renders a clear "no access" page instead of a broken screen. */
export function RequirePerm({
  perm,
  children,
}: {
  perm: PermName | PermName[];
  children: ReactNode;
}) {
  const { canAny } = useAuth();
  const { t } = useTranslation();
  const perms = Array.isArray(perm) ? perm : [perm];
  if (canAny(...perms)) return <>{children}</>;
  return (
    <Center mih="60vh">
      <Stack align="center" gap="xs" maw={420} ta="center">
        <IconLock size={36} stroke={1.5} color="var(--ck-decor)" />
        <Title order={2}>{t('You do not have access to this page')}</Title>
        <Text c="dimmed">{t('Ask the owner if you need this for your work.')}</Text>
        <Button component={Link} to="/" variant="default" mt="sm">
          {t('Go to dashboard')}
        </Button>
      </Stack>
    </Center>
  );
}
