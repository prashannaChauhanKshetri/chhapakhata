import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { modals } from '@mantine/modals';
import { IconAlertCircle, IconFileInvoice } from '@tabler/icons-react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { ApiError } from '@/api/errors';
import { apiGet } from '@/api/http';
import type { UnbilledOrder } from '@/api/types';
import { TableSkeleton } from '@/components/Skeletons';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatNPR, formatQty, toNumber } from '@/lib/format';

import { useShopSettings } from '../orders/useCatalog';

interface MakeBillProps {
  customerId: number;
  /** Orders ticked when the window opens (e.g. the order the bill was started from). */
  preselect?: number[];
  onDone: (invoiceId?: number) => void;
}

/**
 * Make a bill: one or more of a customer's orders, from one order to another or
 * ticked one by one, with VAT added or not. VAT is worked out once on the total.
 */
export function MakeBillForm({ customerId, preselect = [], onDone }: MakeBillProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data: shop } = useShopSettings();
  const [selected, setSelected] = useState<number[]>(preselect);
  const [addVat, setAddVat] = useState<boolean | null>(null); // null: the bill's default
  const [vatNote, setVatNote] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);

  const { data: orders, error } = useQuery({
    queryKey: ['customer', customerId, 'unbilled-orders'],
    queryFn: () => apiGet<UnbilledOrder[]>(`/api/v1/customers/${customerId}/unbilled-orders/`),
  });

  // Oldest first, as the bill lists them.
  const chosen = useMemo(
    () => (orders ?? []).filter((o) => selected.includes(o.id)).map((o) => o.id),
    [orders, selected],
  );
  const [debounced] = useDebouncedValue({ chosen, addVat }, 250);
  const preview = useQuery({
    queryKey: ['bill-preview', customerId, debounced],
    queryFn: () =>
      unwrap(
        api.POST('/api/v1/invoices/preview/', {
          body: { customer: customerId, orders: debounced.chosen, add_vat: debounced.addVat },
        }),
      ),
    enabled: debounced.chosen.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const totals = chosen.length ? preview.data : undefined;
  const vatOn = addVat ?? totals?.default_add_vat ?? false;
  const previewError = preview.error instanceof ApiError ? preview.error : null;

  const options = (orders ?? []).map((o) => ({
    value: String(o.id),
    label: `${o.order_no} · ${o.order_date_bs}`,
  }));
  const pickRange = (start: string | null, end: string | null) => {
    setFrom(start);
    setTo(end);
    if (!orders || !start) return;
    const a = orders.findIndex((o) => String(o.id) === start);
    const b = end ? orders.findIndex((o) => String(o.id) === end) : a;
    const [lo, hi] = a <= b ? [a, b] : [b, a];
    setSelected(orders.slice(lo, hi + 1).map((o) => o.id));
  };
  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const make = async () => {
    setBusy(true);
    try {
      const invoice = await unwrap(
        api.POST('/api/v1/invoices/', {
          body: {
            customer: customerId,
            orders: chosen,
            add_vat: vatOn,
            vat_note: vatOn ? '' : vatNote.trim(),
            notes: notes.trim(),
          },
        }),
      );
      await Promise.all(
        ['invoices', 'order', 'orders', 'customer', 'customers', 'dashboard'].map((k) =>
          client.invalidateQueries({ queryKey: [k] }),
        ),
      );
      notifySuccess(t('Bill {{no}} made', { no: invoice.invoice_no }));
      onDone(invoice.id);
    } catch (err) {
      notifyError(err, t('Bill not made'));
    } finally {
      setBusy(false);
    }
  };

  if (error) return <Alert color="red">{t('Could not load the orders.')}</Alert>;
  if (!orders) return <TableSkeleton rows={5} />;
  if (orders.length === 0) {
    return (
      <Stack>
        <Text size="sm">{t('Every order of this customer is already billed.')}</Text>
        <Group justify="flex-end">
          <Button onClick={() => onDone()}>{t('Close')}</Button>
        </Group>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
        <Select
          label={t('From order')}
          placeholder={t('First order on the bill')}
          data={options}
          value={from}
          searchable
          onChange={(v) => pickRange(v, to)}
        />
        <Select
          label={t('To order')}
          placeholder={t('Last order on the bill')}
          data={options}
          value={to}
          searchable
          onChange={(v) => pickRange(from, v)}
        />
      </SimpleGrid>

      <ScrollArea.Autosize mah={300} type="auto">
        <Table striped highlightOnHover verticalSpacing={6} horizontalSpacing="xs" fz="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={36}>
                <Checkbox
                  aria-label={t('All orders')}
                  checked={chosen.length === orders.length}
                  indeterminate={chosen.length > 0 && chosen.length < orders.length}
                  onChange={() =>
                    setSelected(chosen.length === orders.length ? [] : orders.map((o) => o.id))
                  }
                />
              </Table.Th>
              <Table.Th>{t('Order')}</Table.Th>
              <Table.Th visibleFrom="sm">{t('Date (BS)')}</Table.Th>
              <Table.Th visibleFrom="sm">{t('Items')}</Table.Th>
              <Table.Th ta="right">{t('Before VAT')}</Table.Th>
              <Table.Th ta="right" visibleFrom="sm">
                {t('Paid')}
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {orders.map((o) => (
              <Table.Tr
                key={o.id}
                onClick={() => toggle(o.id)}
                style={{ cursor: 'pointer' }}
                bg={selected.includes(o.id) ? 'var(--mantine-primary-color-light)' : undefined}
              >
                <Table.Td>
                  <Checkbox
                    aria-label={o.order_no}
                    checked={selected.includes(o.id)}
                    onChange={() => toggle(o.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Table.Td>
                <Table.Td>
                  <Group gap={6} style={{ rowGap: 2 }}>
                    <Text size="sm" fw={500} style={{ whiteSpace: 'nowrap' }}>
                      {o.order_no}
                    </Text>
                    {o.source === 'import' && (
                      <Badge size="xs" variant="light" color="gray">
                        {t('Work log')}
                      </Badge>
                    )}
                  </Group>
                  {/* On a phone the date and items sit under the order number. */}
                  <Text size="xs" c="dimmed" hiddenFrom="sm" lineClamp={2}>
                    {o.order_date_bs} · {o.items}
                  </Text>
                </Table.Td>
                <Table.Td visibleFrom="sm">{o.order_date_bs}</Table.Td>
                <Table.Td maw={220} visibleFrom="sm">
                  <Text size="sm" truncate>
                    {o.items}
                  </Text>
                </Table.Td>
                <Table.Td ta="right" className="num">
                  {formatAmount(o.taxable_amount)}
                </Table.Td>
                <Table.Td ta="right" className="num" visibleFrom="sm">
                  {toNumber(o.paid_amount) > 0 ? formatAmount(o.paid_amount) : '—'}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea.Autosize>

      {shop?.is_vat_registered && (
        <Stack gap={6}>
          <Switch
            label={t('Add VAT {{rate}}%', { rate: formatQty(shop.vat_rate) })}
            description={t(
              'Added once on the bill total. VAT already shown on an order is not added again.',
            )}
            checked={vatOn}
            onChange={(e) => setAddVat(e.currentTarget.checked)}
          />
          {!vatOn && (
            <TextInput
              label={t('Reason VAT is not added (optional)')}
              placeholder={t('e.g. Exempt, or the customer asked for a bill without VAT')}
              maxLength={255}
              value={vatNote}
              onChange={(e) => setVatNote(e.currentTarget.value)}
            />
          )}
        </Stack>
      )}
      <TextInput
        label={t('Note on the bill (optional)')}
        maxLength={255}
        value={notes}
        onChange={(e) => setNotes(e.currentTarget.value)}
      />

      {previewError && (
        <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />}>
          {previewError.summary}
        </Alert>
      )}
      {totals && (
        <Stack gap={4} p="sm" bg="var(--mantine-color-default-hover)" style={{ borderRadius: 8 }}>
          <Group justify="space-between">
            <Text size="sm">
              {t('{{n}} orders', { n: totals.orders.length })}
              {totals.orders.length > 1
                ? ` · ${totals.orders[0].order_no} – ${totals.orders[totals.orders.length - 1].order_no}`
                : ` · ${totals.orders[0]?.order_no ?? ''}`}
            </Text>
          </Group>
          <Row label={t('Sub-total')} value={totals.subtotal} />
          {toNumber(totals.discount_amount) > 0 && (
            <Row label={t('Discount')} value={`-${totals.discount_amount}`} />
          )}
          {totals.add_vat && (
            <>
              <Row label={t('Taxable amount')} value={totals.taxable_amount} />
              <Row
                label={t('VAT {{rate}}%', { rate: formatQty(totals.vat_rate) })}
                value={totals.vat_amount}
              />
            </>
          )}
          {toNumber(totals.round_off) !== 0 && (
            <Row label={t('Round off')} value={totals.round_off} />
          )}
          <Group justify="space-between">
            <Text fw={700}>{t('Bill total')}</Text>
            <Text fw={700} fz="lg" className="num">
              {formatNPR(totals.total)}
            </Text>
          </Group>
          {toNumber(totals.work_on_account) > 0 && (
            <Text size="xs" c="dimmed">
              {t(
                '{{amount}} of work-log orders is already on the account and moves onto this bill, so the balance goes up by {{change}}.',
                {
                  amount: formatNPR(totals.work_on_account),
                  change: formatNPR(totals.account_change),
                },
              )}
            </Text>
          )}
        </Stack>
      )}

      <Group justify="flex-end">
        <Button variant="default" onClick={() => onDone()}>
          {t('Cancel')}
        </Button>
        <Button
          leftSection={<IconFileInvoice size={16} />}
          disabled={!chosen.length || !!previewError || preview.isFetching}
          loading={busy}
          onClick={() => void make()}
        >
          {t('Make bill')}
        </Button>
      </Group>
      <Text size="xs" c="dimmed" ta="right">
        {t('A bill cannot be deleted; the owner can cancel it with a reason.')}
      </Text>
    </Stack>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Group justify="space-between">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text size="sm" className="num">
        {formatAmount(value)}
      </Text>
    </Group>
  );
}

export function openMakeBill({
  customerId,
  customerName,
  preselect,
  onMade,
}: {
  customerId: number;
  customerName: string;
  preselect?: number[];
  onMade?: (invoiceId: number) => void;
}) {
  const id = modals.open({
    title: `Make a bill · ${customerName}`,
    size: 'xl',
    children: (
      <MakeBillForm
        customerId={customerId}
        preselect={preselect}
        onDone={(invoiceId) => {
          modals.close(id);
          if (invoiceId) onMade?.(invoiceId);
        }}
      />
    ),
  });
}
