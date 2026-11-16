import { Alert, Button, Group, Stack, Table, Text, TextInput } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconCopyOff } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatDate, formatNPR } from '@/lib/format';

const CONFIRM_WORD = 'Confirm';
const QUERY_KEY = ['system', 'duplicate-payments'];

function VoidDuplicatesForm({ count, onDone }: { count: number; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const ready = typed.trim().toLowerCase() === CONFIRM_WORD.toLowerCase();

  const run = async () => {
    setBusy(true);
    try {
      const result = await unwrap(
        api.POST('/api/v1/system/duplicate-payments/', { body: { confirm: typed.trim() } }),
      );
      await client.invalidateQueries();
      notifySuccess(
        t('{{n}} duplicate payments voided ({{amount}}). A backup was taken first.', {
          n: result.voided,
          amount: formatNPR(result.total),
        }),
      );
      onDone();
    } catch (error) {
      notifyError(error, t('Nothing was changed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="md">
      <Text size="sm">
        {t(
          'The {{n}} copies from the payments sheet are voided: they stay on record as "Duplicate of RCT-…", and each customer’s balance and statements are corrected. The payments recorded with the orders are kept. A backup is taken first.',
          { n: count },
        )}
      </Text>
      <TextInput
        label={t('Type {{word}} to void the duplicates', { word: CONFIRM_WORD })}
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
        <Button color="red" disabled={!ready} loading={busy} onClick={() => void run()}>
          {t('Void {{n}} duplicates', { n: count })}
        </Button>
      </Group>
    </Stack>
  );
}

/**
 * Shown only when a payment was recorded twice: with its order (slip or work
 * log) and again from a payments sheet. The owner voids the copies in one go.
 */
export function DuplicatePayments() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => unwrap(api.GET('/api/v1/system/duplicate-payments/')),
  });
  if (!data || data.count === 0) return null;

  const open = () => {
    const id = modals.open({
      title: t('Void duplicate payments'),
      size: 'lg',
      children: <VoidDuplicatesForm count={data.count} onDone={() => modals.close(id)} />,
    });
  };

  return (
    <Alert
      color="red"
      variant="light"
      icon={<IconCopyOff size={20} />}
      title={t('{{n}} payments are recorded twice ({{amount}})', {
        n: data.count,
        amount: formatNPR(data.total),
      })}
    >
      <Stack gap="sm">
        <Text size="sm">
          {t(
            'These payments came with their orders (order slip or work log) and again from a payments sheet, so the customers’ balances are too low. For example:',
          )}
        </Text>
        <Table fz="sm" verticalSpacing={4}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('Customer')}</Table.Th>
              <Table.Th>{t('Date')}</Table.Th>
              <Table.Th ta="right">{t('Amount')}</Table.Th>
              <Table.Th>{t('Recorded as')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.sample.slice(0, 5).map((row) => (
              <Table.Tr key={row.receipt_no}>
                <Table.Td>{row.customer}</Table.Td>
                <Table.Td>{formatDate(row.payment_date)}</Table.Td>
                <Table.Td ta="right" className="num">
                  {formatNPR(row.amount)}
                </Table.Td>
                <Table.Td>
                  {row.original_receipt_no} + {row.receipt_no}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Button color="red" w="fit-content" onClick={open}>
          {t('Void the {{n}} duplicates…', { n: data.count })}
        </Button>
      </Stack>
    </Alert>
  );
}
