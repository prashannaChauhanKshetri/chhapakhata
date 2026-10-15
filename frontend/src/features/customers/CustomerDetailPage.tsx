import {
  Anchor,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  NumberInput,
  Stack,
  Tabs,
  Text,
  Textarea,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import {
  IconAdjustments,
  IconFileSpreadsheet,
  IconPencil,
  IconPlus,
  IconPrinter,
  IconReceipt2,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { DataTable } from 'mantine-datatable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet, withQuery } from '@/api/http';
import type { Customer, OrderList, Paginated, Statement, StatementEntry } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { KeyValue } from '@/components/KeyValue';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';
import { StatusBadge } from '@/components/StatusBadge';
import { handleFormError, notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatDate, formatNPR, toNumber } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { ORDER_STATUS } from '@/lib/status';

import { openReceivePayment } from '../billing/ReceivePaymentForm';
import { openCustomerModal } from './CustomerForm';

function AdjustBalanceForm({ customer, onDone }: { customer: Customer; onDone: () => void }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: { amount: '' as number | string, narration: '' },
    validate: {
      amount: (v) => (toNumber(v) !== 0 ? null : 'Enter a non-zero amount'),
      narration: (v) =>
        v.trim().length >= 5 ? null : 'Write a short reason (at least 5 characters)',
    },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/customers/{id}/adjust-balance/', {
          params: { path: { id: customer.id } },
          body: { amount: String(values.amount), narration: values.narration },
        }),
      );
      await client.invalidateQueries({ queryKey: ['customer', customer.id] });
      await client.invalidateQueries({ queryKey: ['customers'] });
      notifySuccess('Balance adjusted');
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          Positive increases what the customer owes; negative reduces it. The adjustment is recorded
          in the ledger with your name.
        </Text>
        <NumberInput
          label="Amount"
          prefix="Rs. "
          thousandSeparator=","
          decimalScale={2}
          data-autofocus
          {...form.getInputProps('amount')}
        />
        <Textarea label="Reason" {...form.getInputProps('narration')} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Post adjustment
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function StatementPanel({ customerId }: { customerId: number }) {
  const { t } = useTranslation();
  const [range, setRange] = useState<[string | null, string | null]>([
    dayjs().subtract(3, 'month').startOf('month').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD'),
  ]);
  const query = { from: range[0] ?? undefined, to: range[1] ?? undefined };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['customer', customerId, 'statement', query],
    queryFn: () => apiGet<Statement>(`/api/v1/customers/${customerId}/statement/`, query),
    placeholderData: (previous) => previous,
  });
  const exportAs = (kind: 'pdf' | 'xlsx') =>
    openFile(withQuery(`/api/v1/customers/${customerId}/statement/`, { ...query, export: kind }), {
      download: kind === 'xlsx',
    }).catch((e) => notifyError(e, t('Could not create the statement')));

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  const rows: (StatementEntry & { opening?: boolean })[] = data
    ? [
        {
          id: 0,
          date: data.date_from ?? '',
          date_bs: '',
          entry_type: 'opening',
          entry_type_label: t('Opening balance'),
          reference: '',
          narration: t('Balance brought forward'),
          debit: '0',
          credit: '0',
          balance: data.opening_balance,
          opening: true,
        },
        ...data.entries,
      ]
    : [];

  return (
    <Stack gap="md">
      <Group justify="space-between" gap="sm" wrap="wrap">
        <DatePickerInput
          type="range"
          label={t('Period')}
          value={range}
          onChange={(v) => setRange(v as [string | null, string | null])}
          valueFormat="D MMM YYYY"
          maxDate={dayjs().format('YYYY-MM-DD')}
          w={300}
        />
        <Group gap="xs">
          <Button
            variant="default"
            leftSection={<IconPrinter size={16} />}
            onClick={() => void exportAs('pdf')}
          >
            {t('Print statement')}
          </Button>
          <Button
            variant="default"
            leftSection={<IconFileSpreadsheet size={16} />}
            onClick={() => void exportAs('xlsx')}
          >
            {t('Excel')}
          </Button>
        </Group>
      </Group>
      <DataTable<StatementEntry & { opening?: boolean }>
        minHeight={200}
        withTableBorder
        borderRadius="md"
        verticalSpacing="xs"
        fetching={isFetching && !data}
        records={rows}
        idAccessor={(r) => `${r.entry_type}-${r.id}`}
        noRecordsText={t('No transactions in this period')}
        columns={[
          {
            accessor: 'date',
            title: t('Date'),
            render: (r) =>
              r.opening ? (
                <Text size="sm" c="dimmed">
                  —
                </Text>
              ) : (
                <div>
                  <Text size="sm">{r.date_bs} BS</Text>
                  <Text size="xs" c="dimmed">
                    {formatDate(r.date)}
                  </Text>
                </div>
              ),
          },
          {
            accessor: 'narration',
            title: t('Details'),
            render: (r) => (
              <div>
                <Text size="sm" fw={r.opening ? 500 : undefined}>
                  {r.entry_type_label}
                  {r.reference ? ` · ${r.reference}` : ''}
                </Text>
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {r.narration}
                </Text>
              </div>
            ),
          },
          {
            accessor: 'debit',
            title: t('Debit'),
            textAlign: 'right',
            render: (r) =>
              toNumber(r.debit) ? <span className="num">{formatAmount(r.debit)}</span> : '',
          },
          {
            accessor: 'credit',
            title: t('Credit'),
            textAlign: 'right',
            render: (r) =>
              toNumber(r.credit) ? <span className="num">{formatAmount(r.credit)}</span> : '',
          },
          {
            accessor: 'balance',
            title: t('Balance'),
            textAlign: 'right',
            render: (r) => <Money value={r.balance} prefix={false} fw={500} size="sm" />,
          },
        ]}
      />
      {data && (
        <Group justify="flex-end" gap="xl">
          <Text size="sm" c="dimmed">
            {t('Billed')} <Money value={data.total_debit} size="sm" c="slate.9" />
          </Text>
          <Text size="sm" c="dimmed">
            {t('Received')} <Money value={data.total_credit} size="sm" c="slate.9" />
          </Text>
          <Text size="sm" fw={600}>
            {toNumber(data.closing_balance) < 0 ? t('Advance with us') : t('Closing balance')}{' '}
            <Money value={Math.abs(toNumber(data.closing_balance))} size="sm" />
          </Text>
        </Group>
      )}
    </Stack>
  );
}

export default function CustomerDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const customerId = Number(id);
  const navigate = useNavigate();
  const { can } = useAuth();
  const {
    data: customer,
    error,
    refetch,
  } = useQuery({
    queryKey: ['customer', customerId],
    queryFn: () => apiGet<Customer>(`/api/v1/customers/${customerId}/`),
  });
  const { data: orders, isFetching: ordersLoading } = useQuery({
    queryKey: ['orders', { customer: customerId }],
    queryFn: () =>
      apiGet<Paginated<OrderList>>('/api/v1/orders/', { customer: customerId, page_size: 50 }),
    enabled: can(Perm.ORDERS_VIEW),
  });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  if (!customer) return <PageLoader />;
  const balance = toNumber(customer.balance);
  // Work in progress is billed when invoiced; show it so the counter sees the full picture.
  const uninvoiced = (orders?.results ?? [])
    .filter((o) => !o.invoice_no && !['quotation', 'cancelled'].includes(o.status))
    .reduce((sum, o) => sum + toNumber(o.balance_due), 0);

  const adjust = () => {
    const modalId = modals.open({
      title: t('Adjust balance'),
      children: <AdjustBalanceForm customer={customer} onDone={() => modals.close(modalId)} />,
    });
  };

  return (
    <>
      <PageHeader
        back={{ to: '/customers', label: t('Customers') }}
        title={customer.name}
        badge={
          <Group gap={6}>
            <Badge color="slate">{customer.customer_type_label}</Badge>
            {!customer.is_active && <Badge color="red">{t('Inactive')}</Badge>}
          </Group>
        }
        actions={
          <>
            {can(Perm.LEDGER_MANAGE) && (
              <Button
                variant="default"
                leftSection={<IconAdjustments size={16} />}
                onClick={adjust}
              >
                {t('Adjust balance')}
              </Button>
            )}
            {can(Perm.CUSTOMERS_MANAGE) && (
              <Button
                variant="default"
                leftSection={<IconPencil size={16} />}
                onClick={() => openCustomerModal({ customer })}
              >
                {t('Edit')}
              </Button>
            )}
            {can(Perm.PAYMENTS_RECEIVE) && (
              <Button
                variant="default"
                leftSection={<IconReceipt2 size={16} />}
                onClick={() => openReceivePayment({ customer })}
              >
                {t('Receive payment')}
              </Button>
            )}
            {can(Perm.ORDERS_MANAGE) && customer.is_active && (
              <Button
                leftSection={<IconPlus size={16} />}
                onClick={() => navigate(`/orders/new?customer=${customer.id}`)}
              >
                {t('New order')}
              </Button>
            )}
          </>
        }
      />
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap="lg">
            <Card>
              <Text size="sm" c="dimmed" fw={500}>
                {balance < 0 ? t('Advance with us') : t('Balance due')}
              </Text>
              <Money
                value={Math.abs(balance)}
                fz={28}
                fw={600}
                c={balance > 0 ? 'red.7' : 'slate.9'}
                style={{ fontVariantNumeric: 'normal' }}
              />
              <Text size="xs" c="dimmed" mt={4}>
                {t('From the customer ledger, after all invoices and payments.')}
              </Text>
              {uninvoiced > 0 && (
                <Text size="sm" mt="sm" pt="sm" style={{ borderTop: '1px solid var(--ck-border)' }}>
                  {t('Plus {{amount}} on orders not yet invoiced.', {
                    amount: formatNPR(uninvoiced),
                  })}
                </Text>
              )}
            </Card>
            <Card>
              <KeyValue
                labelWidth={110}
                items={[
                  { label: t('Phone'), value: customer.phone || '—' },
                  {
                    label: t('Alt. phone'),
                    value: customer.alt_phone,
                    hidden: !customer.alt_phone,
                  },
                  { label: t('Address'), value: customer.address || '—' },
                  { label: t('PAN / VAT'), value: customer.pan_no || '—' },
                  { label: t('Customer since'), value: `${customer.created_at_bs} BS` },
                  { label: t('Notes'), value: customer.notes, hidden: !customer.notes },
                ]}
              />
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card>
            <Tabs defaultValue={can(Perm.ORDERS_VIEW) ? 'orders' : 'statement'} keepMounted={false}>
              <Tabs.List mb="md">
                {can(Perm.ORDERS_VIEW) && <Tabs.Tab value="orders">{t('Orders')}</Tabs.Tab>}
                {can(Perm.LEDGER_VIEW) && <Tabs.Tab value="statement">{t('Statement')}</Tabs.Tab>}
              </Tabs.List>
              <Tabs.Panel value="orders">
                <DataTable<OrderList>
                  minHeight={200}
                  withTableBorder
                  borderRadius="md"
                  highlightOnHover
                  fetching={ordersLoading && !orders}
                  records={orders?.results ?? []}
                  noRecordsText={t('No orders yet')}
                  onRowClick={({ record }) => navigate(`/orders/${record.id}`)}
                  columns={[
                    {
                      accessor: 'order_no',
                      title: t('Order'),
                      render: (o) => (
                        <Anchor
                          component={Link}
                          to={`/orders/${o.id}`}
                          size="sm"
                          fw={500}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {o.order_no}
                        </Anchor>
                      ),
                    },
                    {
                      accessor: 'order_date',
                      title: t('Date'),
                      render: (o) => `${o.order_date_bs} BS`,
                    },
                    {
                      accessor: 'status',
                      title: t('Status'),
                      render: (o) => <StatusBadge value={o.status} map={ORDER_STATUS} />,
                    },
                    {
                      accessor: 'total',
                      title: t('Total'),
                      textAlign: 'right',
                      render: (o) => <Money value={o.total} prefix={false} size="sm" />,
                    },
                    {
                      accessor: 'balance_due',
                      title: t('Balance'),
                      textAlign: 'right',
                      render: (o) => (
                        <Money value={o.balance_due} prefix={false} tone="due" size="sm" />
                      ),
                    },
                  ]}
                />
              </Tabs.Panel>
              <Tabs.Panel value="statement">
                <StatementPanel customerId={customer.id} />
              </Tabs.Panel>
            </Tabs>
          </Card>
        </Grid.Col>
      </Grid>
    </>
  );
}
