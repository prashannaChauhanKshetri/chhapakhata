import {
  Alert,
  Button,
  Card,
  Checkbox,
  Group,
  List,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconAlertTriangle, IconTrash } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { FormSkeleton } from '@/components/Skeletons';
import { notifyError, notifySuccess } from '@/lib/forms';

const CONFIRM_WORD = 'Confirm';

function EraseForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [keepCatalog, setKeepCatalog] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const { data: rows } = useQuery({
    queryKey: ['system', 'erase-preview'],
    queryFn: () => unwrap(api.GET('/api/v1/system/erase/')),
    staleTime: 0,
  });
  if (!rows) return <FormSkeleton sections={1} />;

  const shown = rows.filter((r) => r.count > 0 && !(keepCatalog && r.catalog));
  const ready = typed.trim().toLowerCase() === CONFIRM_WORD.toLowerCase();

  const erase = async () => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/system/erase/', {
          body: { confirm: typed.trim(), keep_catalog: keepCatalog },
        }),
      );
      await client.invalidateQueries(); // every list and figure on screen is out of date
      notifySuccess(t('All data was deleted. A backup was taken first.'));
      onDone();
    } catch (error) {
      notifyError(error, t('Nothing was deleted'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="md">
      <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
        {t(
          'This permanently deletes the shop’s records so you can enter everything again. It cannot be undone from the app; only the backup taken just before can bring them back.',
        )}
      </Alert>

      <div>
        <Text size="sm" fw={600} mb={4}>
          {t('Will be deleted')}
        </Text>
        {shown.length === 0 ? (
          <Text size="sm" c="dimmed">
            {t('There is nothing to delete.')}
          </Text>
        ) : (
          <List size="sm" spacing={2}>
            {shown.map((r) => (
              <List.Item key={r.title}>
                {t(r.title)}: <b className="num">{r.count.toLocaleString('en-IN')}</b>
              </List.Item>
            ))}
            <List.Item>{t('Bill and receipt numbering starts again from 1')}</List.Item>
          </List>
        )}
        <Text size="sm" c="dimmed" mt="xs">
          {t('Kept: staff logins, shop settings (name, PAN, logo) and the activity log.')}
        </Text>
      </div>

      <Checkbox
        checked={keepCatalog}
        onChange={(e) => setKeepCatalog(e.currentTarget.checked)}
        label={t('Keep the rate card and the stock item list')}
        description={t('Prices and item names stay; stock quantities go to zero.')}
      />

      <TextInput
        label={t('Type {{word}} to delete', { word: CONFIRM_WORD })}
        placeholder={CONFIRM_WORD}
        value={typed}
        onChange={(e) => setTyped(e.currentTarget.value)}
        autoComplete="off"
        data-autofocus
      />

      <Group justify="flex-end">
        <Button variant="default" onClick={onDone}>
          {t('Cancel')}
        </Button>
        <Button
          color="red"
          leftSection={<IconTrash size={16} />}
          disabled={!ready}
          loading={busy}
          onClick={() => void erase()}
        >
          {t('Delete all data')}
        </Button>
      </Group>
    </Stack>
  );
}

/** Owner-only: wipe the shop's records to start entering again (backup first). */
export function EraseDataCard() {
  const { t } = useTranslation();
  const open = () => {
    const id = modals.open({
      title: t('Delete all data'),
      size: 'lg',
      children: <EraseForm onDone={() => modals.close(id)} />,
    });
  };
  return (
    <Card withBorder style={{ borderColor: 'var(--mantine-color-red-4)' }}>
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <ThemeIcon color="red" variant="light" size={36} radius="md">
          <IconTrash size={20} />
        </ThemeIcon>
        <Stack gap={4} style={{ flex: 1 }}>
          <Text fw={600}>{t('Delete all data')}</Text>
          <Text size="sm" c="dimmed">
            {t(
              'Start again with an empty shop: deletes customers, orders, bills, payments, the ledger and stock. Staff logins and shop settings stay. A backup is taken first. Owner only.',
            )}
          </Text>
          <Button mt="xs" w="fit-content" color="red" variant="light" onClick={open}>
            {t('Delete all data…')}
          </Button>
        </Stack>
      </Group>
    </Card>
  );
}
