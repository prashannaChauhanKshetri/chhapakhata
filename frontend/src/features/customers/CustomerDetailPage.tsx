import {
  Anchor,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  NumberInput,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  Textarea,
} from '@mantine/core';
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
import { DataTable } from '@/components/DataTable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet, withQuery } from '@/api/http';
import type { Customer, OrderList, Paginated, Statement, StatementEntry } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Balance } from '@/components/Balance';
import { KeyValue } from '@/components/KeyValue';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { DetailSkeleton } from '@/components/Skeletons';
import {
  PeriodPicker,
  type PeriodValue,
  resolvePeriod,
  usePeriods,
} from '@/components/PeriodPicker';
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

type StatementRow = StatementEntry & { kind?: 'opening' | 'closing' };

const STATEMENT_PAGE_SIZE = 50;

function entryLink(r: StatementEntry): string | null {
  if (r.invoice_id) return `/invoices/${r.invoice_id}`;
  if (r.order_id) return `/orders/${r.order_id}`;
  return null;
}

function StatementPanel({ customerId }: { customerId: number }) {
  const { t } = useTranslation();
  const { data: periods } = usePeriods();
  const [period, setPeriod] = useState<PeriodValue>({ key: 'this_fy', from: null, to: null });
  const [statementPage, setStatementPage] = useState(1);
  const resolved = resolvePeriod(period, periods);
  const waiting = resolved.key !== 'all' && resolved.key !== 'custom' && !resolved.to;
  const query = { from: resolved.from ?? undefined, to: resolved.to ?? undefined };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['customer', customerId, 'statement', query],
    queryFn: () => apiGet<Statement>(`/api/v1/customers/${customerId}/statement/`, query),
    placeholderData: (previous) => previous,
    enabled: !waiting,
  });
  const exportAs = (kind: 'pdf' | 'xlsx') =>
    openFile(withQuery(`/api/v1/customers/${customerId}/statement/`, { ...query, export: kind }), {
      download: kind === 'xlsx',
    }).catch((e) => notifyError(e, t('Could not create the statement')));

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  const blank = { reference: '', invoice_id: null, payment_id: null, order_id: null };
  // Long statements are paged; opening sits on the first page, closing on the last.
  const entries = data?.entries ?? [];
  const pages = Math.max(1, Math.ceil(entries.length / STATEMENT_PAGE_SIZE));
  const page = Math.min(statementPage, pages);
  const pageEntries = entries.slice((page - 1) * STATEMENT_PAGE_SIZE, page * STATEMENT_PAGE_SIZE);
  const rows: StatementRow[] = data
    ? [
        ...(page === 1
          ? [
              {
                ...blank,
                id: -1,
                kind: 'opening',
                date: data.date_from ?? '',
                date_bs: '',
                entry_type: 'opening',
                entry_type_label: t('Opening balance'),
                narration: data.date_from ? t('Brought forward') : t('Start of the ledger'),
                debit: '0',
                credit: '0',
                balance: data.opening_balance,
              } satisfies StatementRow,
            ]
          : []),
        ...pageEntries,
        ...(page === pages
          ? [
              {
                ...blank,
                id: -2,
                kind: 'closing',
                date: data.date_to,
                date_bs: '',
                entry_type: 'closing',
                entry_type_label: t('Closing balance'),
                narration: t('Carried forward'),
                debit: data.total_debit,
                credit: data.total_credit,
                balance: data.closing_balance,
              } satisfies StatementRow,
            ]
          : []),
      ]
    : [];
  const closing = toNumber(data?.closing_balance);
  const aging = data?.aging?.buckets.filter((b) => toNumber(b.amount) > 0) ?? [];

  return (
    <Stack gap="md">
      <Group justify="space-between" gap="sm" wrap="wrap" align="flex-end">
        <PeriodPicker
          value={period}
          onChange={(next) => {
            setPeriod(next);
            setStatementPage(1);
          }}
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

      {data && (
        <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm">
          <StatementFigure
            label={t('Opening balance')}
            hint={
              data.date_from ? t('on {{date}}', { date: formatDate(data.date_from) }) : undefined
            }
          >
            <Balance value={data.opening_balance} />
          </StatementFigure>
          <StatementFigure label={t('Billed (Dr)')}>
            <Money value={data.total_debit} prefix={false} />
          </StatementFigure>
          <StatementFigure label={t('Received (Cr)')}>
            <Money value={data.total_credit} prefix={false} />
          </StatementFigure>
          <StatementFigure
            label={t('Closing balance')}
            hint={
              closing > 0
                ? t('Customer owes the shop')
                : closing < 0
                  ? t('Advance with the shop')
                  : t('Settled')
            }
            strong
          >
            <Balance value={data.closing_balance} c={closing > 0 ? 'red.7' : undefined} />
          </StatementFigure>
        </SimpleGrid>
      )}

      {data && (data.by_type.length > 0 || aging.length > 0) && (
        <Group gap="lg" wrap="wrap">
          {data.by_type.length > 0 && (
            <Text size="xs" c="dimmed">
              {data.by_type
                .map(
                  (b) =>
                    `${b.label} ${b.count} · ${formatAmount(toNumber(b.debit) || toNumber(b.credit))}`,
                )
                .join('   |   ')}
            </Text>
          )}
          {aging.length > 0 && (
            <Text size="xs" c="dimmed">
              {t('Due by age')}:{' '}
              {aging.map((b) => `${b.label} days ${formatAmount(b.amount)}`).join(' · ')}
            </Text>
          )}
        </Group>
      )}

      <DataTable<StatementRow>
        minHeight={200}
        withTableBorder
        verticalSpacing="xs"
        fetching={isFetching && !data}
        records={rows}
        totalRecords={entries.length}
        recordsPerPage={STATEMENT_PAGE_SIZE}
        page={page}
        onPageChange={setStatementPage}
        // Count ledger entries only, not the opening and closing rows.
        paginationText={({ totalRecords }) =>
          t('Entries {{from}}–{{to}} of {{total}}', {
            from: totalRecords ? (page - 1) * STATEMENT_PAGE_SIZE + 1 : 0,
            to: Math.min(page * STATEMENT_PAGE_SIZE, totalRecords),
            total: totalRecords,
          })
        }
        idAccessor={(r) => `${r.entry_type}-${r.id}`}
        rowStyle={(r) =>
          r.kind ? { background: 'var(--mantine-color-slate-0)', fontWeight: 500 } : undefined
        }
        noRecordsText={t('No transactions in this period')}
        columns={[
          {
            accessor: 'date',
            title: t('Date'),
            width: 130,
            render: (r) =>
              r.kind ? (
                <Text size="sm" c="dimmed">
                  {r.date ? formatDate(r.date) : '—'}
                </Text>
              ) : (
                <div>
                  <Text size="sm" style={{ whiteSpace: 'nowrap' }}>
                    {r.date_bs} BS
                  </Text>
                  <Text size="xs" c="dimmed">
                    {formatDate(r.date)}
                  </Text>
                </div>
              ),
          },
          {
            accessor: 'narration',
            title: t('Particulars'),
            render: (r) => {
              const link = entryLink(r);
              return (
                <div>
                  <Text size="sm" fw={r.kind ? 600 : undefined}>
                    {r.entry_type_label}
                    {r.reference && (
                      <>
                        {' · '}
                        {link ? (
                          <Anchor component={Link} to={link} size="sm">
                            {r.reference}
                          </Anchor>
                        ) : (
                          r.reference
                        )}
                      </>
                    )}
                  </Text>
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {r.narration}
                  </Text>
                </div>
              );
            },
          },
          {
            accessor: 'debit',
            title: t('Debit'),
            textAlign: 'right',
            render: (r) =>
              r.kind !== 'opening' && toNumber(r.debit) ? (
                <span className="num">{formatAmount(r.debit)}</span>
              ) : (
                ''
              ),
          },
          {
            accessor: 'credit',
            title: t('Credit'),
            textAlign: 'right',
            render: (r) =>
              r.kind !== 'opening' && toNumber(r.credit) ? (
                <span className="num">{formatAmount(r.credit)}</span>
              ) : (
                ''
              ),
          },
          {
            accessor: 'balance',
            title: t('Balance'),
            textAlign: 'right',
            render: (r) => <Balance value={r.balance} size="sm" fw={r.kind ? 600 : 500} />,
          },
        ]}
      />
    </Stack>
  );
}

function StatementFigure({
  label,
  hint,
  strong,
  children,
}: {
  label: string;
  hint?: string;
  strong?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card padding="sm" withBorder bg={strong ? 'slate.0' : undefined}>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text fz={20} fw={600} lh={1.3}>
        {children}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </Card>
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
  if (!customer) return <DetailSkeleton />;
  const balance = toNumber(customer.balance);
  // Work in progress is billed when invoiced; show it so the counter sees the full picture.
  // Imported work-log orders are already charged to the ledger, so they are not counted.
  const uninvoiced = (orders?.results ?? [])
    .filter(
      (o) =>
        !o.invoice_no && o.source !== 'import' && !['quotation', 'cancelled'].includes(o.status),
    )
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
                variant="light"
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
