import {
  Anchor,
  Button,
  Card,
  Group,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconFileSpreadsheet, IconPrinter, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { openFile } from '@/api/files';
import { apiGet, withQuery } from '@/api/http';
import type { LedgerEntry, LedgerSummary, LedgerSummaryRow, Paginated } from '@/api/types';
import { Balance } from '@/components/Balance';
import { DualDate } from '@/components/DualDate';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import {
  PeriodPicker,
  type PeriodValue,
  resolvePeriod,
  usePeriods,
} from '@/components/PeriodPicker';
import { QueryError } from '@/components/QueryError';
import { StatCard } from '@/components/StatCard';
import { notifyError } from '@/lib/forms';
import { formatAmount, formatDate, formatNPRCompact, toNumber } from '@/lib/format';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

const ENTRY_TYPES = [
  { value: 'opening', label: 'Opening balance' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'invoice_cancel', label: 'Invoice cancelled' },
  { value: 'imported_work', label: 'Work (imported)' },
  { value: 'payment', label: 'Payment received' },
  { value: 'payment_void', label: 'Payment voided' },
  { value: 'adjustment', label: 'Adjustment' },
];

function usePeriod(initial: string) {
  const { data: periods } = usePeriods();
  const [period, setPeriod] = useState<PeriodValue>({ key: initial, from: null, to: null });
  const resolved = resolvePeriod(period, periods);
  const ready = resolved.key === 'all' || resolved.key === 'custom' || !!resolved.to;
  return { period, setPeriod, resolved, ready };
}

function BalancesTab() {
  const { t } = useTranslation();
  const { period, setPeriod, resolved, ready } = usePeriod('this_fy');
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 300);
  const [balance, setBalance] = useState('');
  const query = {
    from: resolved.from ?? undefined,
    to: resolved.to ?? undefined,
    search: debounced || undefined,
    balance: balance || undefined,
  };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['ledger', 'summary', query],
    queryFn: () => apiGet<LedgerSummary>('/api/v1/ledger/summary/', query),
    placeholderData: (previous) => previous,
    enabled: ready,
  });
  const exportAs = (kind: 'pdf' | 'xlsx') =>
    openFile(withQuery('/api/v1/ledger/summary/', { ...query, export: kind }), {
      download: kind === 'xlsx',
    }).catch((e) => notifyError(e, t('Could not create the file')));

  const totals = data?.totals;
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm">
        <StatCard
          label={t('Opening balance')}
          loading={!totals}
          value={formatNPRCompact(totals?.opening_balance)}
          hint={resolved.from ? t('on {{date}}', { date: formatDate(resolved.from) }) : undefined}
        />
        <StatCard
          label={t('Billed in period')}
          loading={!totals}
          value={formatNPRCompact(totals?.debit)}
        />
        <StatCard
          label={t('Received in period')}
          loading={!totals}
          value={formatNPRCompact(totals?.credit)}
        />
        <StatCard
          label={t('Closing receivable')}
          loading={!totals}
          value={formatNPRCompact(totals?.receivable)}
          tone={toNumber(totals?.receivable) > 0 ? 'danger' : 'default'}
          hint={
            toNumber(totals?.advances) > 0
              ? t('Advances held {{amount}}', { amount: formatAmount(totals?.advances) })
              : t('{{n}} customers', { n: totals?.customers ?? 0 })
          }
        />
      </SimpleGrid>

      <Card padding={0}>
        <Group p="md" gap="sm" wrap="wrap" align="flex-end">
          <PeriodPicker value={period} onChange={setPeriod} />
          <TextInput
            label={t('Customer')}
            placeholder={t('Name or phone')}
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            w={220}
          />
          <SegmentedControl
            value={balance}
            onChange={setBalance}
            data={[
              { value: '', label: t('All') },
              { value: 'due', label: t('Due') },
              { value: 'advance', label: t('Advance') },
              { value: 'settled', label: t('Settled') },
            ]}
          />
          <Group gap="xs" ml="auto">
            <Button
              variant="default"
              leftSection={<IconPrinter size={16} />}
              onClick={() => void exportAs('pdf')}
            >
              {t('Print')}
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
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<LedgerSummaryRow>
            minHeight={260}
            highlightOnHover
            idAccessor="customer_id"
            records={data?.rows ?? []}
            fetching={isFetching && !data}
            noRecordsText={t('No customer had ledger activity or a balance in this period')}
            columns={[
              {
                accessor: 'customer_name',
                title: t('Customer'),
                render: (r) => (
                  <div>
                    <Anchor component={Link} to={`/customers/${r.customer_id}`} size="sm" fw={500}>
                      {r.customer_name}
                    </Anchor>
                    <Text size="xs" c="dimmed">
                      {[r.phone, r.address].filter(Boolean).join(' · ') || '—'}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'opening_balance',
                title: t('Opening'),
                textAlign: 'right',
                render: (r) => <Balance value={r.opening_balance} size="sm" />,
              },
              {
                accessor: 'debit',
                title: t('Billed (Dr)'),
                textAlign: 'right',
                render: (r) =>
                  toNumber(r.debit) ? <Money value={r.debit} prefix={false} size="sm" /> : '',
              },
              {
                accessor: 'credit',
                title: t('Received (Cr)'),
                textAlign: 'right',
                render: (r) =>
                  toNumber(r.credit) ? <Money value={r.credit} prefix={false} size="sm" /> : '',
              },
              {
                accessor: 'closing_balance',
                title: t('Closing'),
                textAlign: 'right',
                render: (r) => (
                  <Balance
                    value={r.closing_balance}
                    size="sm"
                    fw={600}
                    c={toNumber(r.closing_balance) > 0 ? 'red.7' : undefined}
                  />
                ),
              },
              {
                accessor: 'last_payment_date',
                title: t('Last payment'),
                visibleMediaQuery: '(min-width: 62em)',
                render: (r) => (
                  <Text size="sm" c={r.last_payment_date ? undefined : 'dimmed'}>
                    {r.last_payment_date ? formatDate(r.last_payment_date) : t('None')}
                  </Text>
                ),
              },
            ]}
          />
        )}
        {totals && totals.customers > 0 && (
          <Group justify="flex-end" gap="xl" p="md" className="num">
            <Text size="sm" c="dimmed">
              {t('Opening')} <Balance value={totals.opening_balance} c="slate.9" />
            </Text>
            <Text size="sm" c="dimmed">
              {t('Billed')} <Money value={totals.debit} prefix={false} c="slate.9" />
            </Text>
            <Text size="sm" c="dimmed">
              {t('Received')} <Money value={totals.credit} prefix={false} c="slate.9" />
            </Text>
            <Text size="sm" fw={600}>
              {t('Closing')} <Balance value={totals.closing_balance} />
            </Text>
          </Group>
        )}
      </Card>
    </Stack>
  );
}

function referenceLink(e: LedgerEntry): string | null {
  if (e.invoice_id) return `/invoices/${e.invoice_id}`;
  if (e.order_id) return `/orders/${e.order_id}`;
  if (e.payment_id) return `/payments?q=${encodeURIComponent(e.reference)}`;
  return null;
}

function DayBookTab() {
  const { t } = useTranslation();
  const list = useListState(['entry_type'] as const, '-entry_date');
  const { period, setPeriod, resolved } = usePeriod('this_month');
  const query = {
    ...list.query,
    date_from: resolved.from ?? undefined,
    date_to: resolved.to ?? undefined,
  };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['ledger', 'entries', query],
    queryFn: () => apiGet<Paginated<LedgerEntry>>('/api/v1/ledger/', query),
    placeholderData: (previous) => previous,
  });

  return (
    <Card padding={0}>
      <Group p="md" gap="sm" wrap="wrap" align="flex-end">
        <PeriodPicker value={period} onChange={setPeriod} />
        <TextInput
          label={t('Search')}
          placeholder={t('Customer, phone or details')}
          leftSection={<IconSearch size={16} />}
          value={list.search}
          onChange={(e) => list.setSearch(e.currentTarget.value)}
          style={{ flex: '1 1 220px' }}
        />
        <Select
          label={t('Type')}
          placeholder={t('All entries')}
          clearable
          w={200}
          data={ENTRY_TYPES.map((e) => ({ ...e, label: t(e.label) }))}
          value={list.filters.entry_type || null}
          onChange={(v) => list.setFilter('entry_type', v)}
        />
      </Group>
      {error ? (
        <Stack p="md">
          <QueryError error={error} onRetry={() => void refetch()} />
        </Stack>
      ) : (
        <DataTable<LedgerEntry>
          minHeight={260}
          highlightOnHover
          records={data?.results ?? []}
          fetching={isFetching && !data}
          totalRecords={data?.count ?? 0}
          recordsPerPage={PAGE_SIZE}
          page={list.page}
          onPageChange={list.setPage}
          sortStatus={list.sortStatus as never}
          onSortStatusChange={list.setSort as never}
          noRecordsText={t('No ledger entries in this period')}
          columns={[
            {
              accessor: 'entry_date',
              title: t('Date'),
              sortable: true,
              render: (e) => <DualDate ad={e.entry_date} bs={e.entry_date_bs} />,
            },
            {
              accessor: 'customer',
              title: t('Customer'),
              render: (e) => (
                <Anchor component={Link} to={`/customers/${e.customer.id}`} size="sm">
                  {e.customer.name}
                </Anchor>
              ),
            },
            {
              accessor: 'narration',
              title: t('Particulars'),
              render: (e) => {
                const link = referenceLink(e);
                return (
                  <div>
                    <Text size="sm">
                      {e.entry_type_label}
                      {e.reference && (
                        <>
                          {' · '}
                          {link ? (
                            <Anchor component={Link} to={link} size="sm">
                              {e.reference}
                            </Anchor>
                          ) : (
                            e.reference
                          )}
                        </>
                      )}
                    </Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>
                      {e.narration}
                      {e.created_by ? ` · ${e.created_by.full_name || e.created_by.username}` : ''}
                    </Text>
                  </div>
                );
              },
            },
            {
              accessor: 'debit',
              title: t('Debit'),
              sortable: true,
              textAlign: 'right',
              render: (e) =>
                toNumber(e.debit) ? <Money value={e.debit} prefix={false} size="sm" /> : '',
            },
            {
              accessor: 'credit',
              title: t('Credit'),
              sortable: true,
              textAlign: 'right',
              render: (e) =>
                toNumber(e.credit) ? <Money value={e.credit} prefix={false} size="sm" /> : '',
            },
          ]}
        />
      )}
    </Card>
  );
}

export default function LedgerPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tab = 'balances' } = useParams();
  return (
    <>
      <PageHeader
        title={t('Ledger')}
        description={t(
          'Every customer’s opening balance, billing, payments and closing balance. Dr = owes the shop, Cr = advance.',
        )}
      />
      <Tabs value={tab} onChange={(v) => v && navigate(`/ledger/${v}`)} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="balances">{t('Customer balances')}</Tabs.Tab>
          <Tabs.Tab value="day-book">{t('Day book')}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="balances">
          <BalancesTab />
        </Tabs.Panel>
        <Tabs.Panel value="day-book">
          <DayBookTab />
        </Tabs.Panel>
      </Tabs>
    </>
  );
}
