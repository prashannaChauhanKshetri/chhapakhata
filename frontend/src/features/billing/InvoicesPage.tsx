import { Anchor, Card, Group, SegmentedControl, Stack, Text, TextInput } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { apiGet } from '@/api/http';
import type { InvoiceList, Paginated } from '@/api/types';
import { DualDate } from '@/components/DualDate';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { StatusBadge } from '@/components/StatusBadge';
import { INVOICE_STATUS } from '@/lib/status';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

export default function InvoicesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const list = useListState(['status'] as const, '-invoice_date');
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['invoices', list.query],
    queryFn: () => apiGet<Paginated<InvoiceList>>('/api/v1/invoices/', list.query),
    placeholderData: (previous) => previous,
  });

  return (
    <>
      <PageHeader
        title={t('Invoices')}
        description={t(
          'Numbered per fiscal year. Invoices are cancelled with a reason, never deleted.',
        )}
      />
      <Card padding={0}>
        <Group p="md" gap="sm" wrap="wrap">
          <TextInput
            placeholder={t('Invoice no., customer, phone or order')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 260px' }}
            aria-label={t('Search invoices')}
          />
          <SegmentedControl
            value={list.filters.status || 'all'}
            onChange={(v) => list.setFilter('status', v === 'all' ? null : v)}
            data={[
              { value: 'all', label: t('All') },
              { value: 'issued', label: t('Issued') },
              { value: 'cancelled', label: t('Cancelled') },
            ]}
          />
        </Group>
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<InvoiceList>
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
            noRecordsText={t('No invoices yet')}
            onRowClick={({ record }) => navigate(`/invoices/${record.id}`)}
            columns={[
              {
                accessor: 'invoice_no',
                title: t('Invoice'),
                render: (i) => (
                  <div>
                    <Anchor
                      component={Link}
                      to={`/invoices/${i.id}`}
                      size="sm"
                      fw={500}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {i.invoice_no}
                    </Anchor>
                    <Text size="xs" c="dimmed">
                      {i.order.order_no}
                      {i.print_count > 0 ? ` · ${t('printed {{n}}×', { n: i.print_count })}` : ''}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'invoice_date',
                title: t('Date'),
                sortable: true,
                render: (i) => <DualDate ad={i.invoice_date} bs={i.invoice_date_bs} />,
              },
              {
                accessor: 'customer_name',
                title: t('Customer'),
                render: (i) => (
                  <div>
                    <Text size="sm" lineClamp={1}>
                      {i.customer_name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {i.customer_phone}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'status',
                title: t('Status'),
                render: (i) => <StatusBadge value={i.status} map={INVOICE_STATUS} />,
              },
              {
                accessor: 'total',
                title: t('Total'),
                sortable: true,
                textAlign: 'right',
                render: (i) => (
                  <Money
                    value={i.total}
                    prefix={false}
                    size="sm"
                    td={i.status === 'cancelled' ? 'line-through' : undefined}
                  />
                ),
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
