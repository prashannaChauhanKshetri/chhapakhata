import { Alert, Button, Group, Text } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { errorMessage } from '@/api/errors';

export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <Alert
      color="red"
      variant="light"
      icon={<IconAlertTriangle size={18} />}
      title={t('Could not load')}
    >
      <Group justify="space-between" gap="sm">
        <Text size="sm">{errorMessage(error)}</Text>
        {onRetry && (
          <Button size="xs" variant="default" onClick={onRetry}>
            {t('Try again')}
          </Button>
        )}
      </Group>
    </Alert>
  );
}
