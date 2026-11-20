import { Alert, Button, Group, Stack, Text } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconFileSpreadsheet, IconPrinter } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { openFile } from '@/api/files';
import { withQuery } from '@/api/http';
import type { Customer } from '@/api/types';
import { notifyError } from '@/lib/forms';
import { todayISO } from '@/lib/format';

import { CustomerSelect } from '../customers/CustomerSelect';
import { OrderDateField } from './OrderDateField';

/** Print orders from one date to another, item by item (PDF or Excel). */
export function PrintOrdersForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const [from, setFrom] = useState(dayjs().subtract(6, 'day').format('YYYY-MM-DD'));
  const [to, setTo] = useState(todayISO());
  const [customer, setCustomer] = useState<Customer | null>(null);
  const wrong = from > to;

  const open = (kind: 'pdf' | 'xlsx') =>
    openFile(
      withQuery('/api/v1/orders/print/', {
        from,
        to,
        customer: customer?.id,
        export: kind,
      }),
      { download: kind === 'xlsx' },
    ).catch((e) => notifyError(e, t('Could not print the orders')));

  return (
    <Stack gap="md">
      <OrderDateField value={from} onChange={setFrom} label={t('From')} showHint={false} />
      <OrderDateField value={to} onChange={setTo} label={t('To')} showHint={false} />
      <CustomerSelect label={t('Customer (optional)')} value={customer} onChange={setCustomer} />
      <Text size="xs" c="dimmed">
        {t(
          'Every confirmed order in these days, item by item (size, sq ft, qty, rate, amount), with each order’s total. Quotations and cancelled orders are left out.',
        )}
      </Text>
      {wrong && <Alert color="red">{t('The From date is after the To date.')}</Alert>}
      <Group justify="flex-end">
        <Button variant="default" onClick={onDone}>
          {t('Close')}
        </Button>
        <Button
          variant="default"
          leftSection={<IconFileSpreadsheet size={16} />}
          disabled={wrong}
          onClick={() => void open('xlsx')}
        >
          {t('Excel')}
        </Button>
        <Button
          leftSection={<IconPrinter size={16} />}
          disabled={wrong}
          onClick={() => void open('pdf')}
        >
          {t('Print')}
        </Button>
      </Group>
    </Stack>
  );
}

export function openPrintOrders() {
  const id = modals.open({
    title: 'Print orders',
    size: 'lg',
    children: <PrintOrdersForm onDone={() => modals.close(id)} />,
  });
}
