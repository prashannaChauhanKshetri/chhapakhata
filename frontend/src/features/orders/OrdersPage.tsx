import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  SegmentedControl,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconFileSpreadsheet, IconPlus, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { apiGet } from '@/api/http';
import type { OrderList, Paginated } from '@/api/types';
import { Can } from '@/auth/Can';
import { DualDate } from '@/components/DualDate';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { StatusBadge } from '@/components/StatusBadge';
import { deadlineLabel } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { ORDER_STATUS } from '@/lib/status';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

const VIEWS = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'quotation', label: 'Quotations' },
  { value: 'ready', label: 'Ready' },
  { value: 'due', label: 'Unpaid' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'cancelled', label: 'Cancelled' },
];

function viewQuery(view: string): Record<string, string> {
  switch (view) {
    case 'open':
      return { status: 'confirmed,in_production,ready' };
    case 'due':
      return { has_balance: 'true' };
    case 'all':
    case '':
      return {};
    default:
      return { status: view };
  }
}

export default function OrdersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const list = useListState(['view'] as const, '-created_at');
  const view = list.filters.view || 'all';
  const { view: _ignored, ...baseQuery } = list.query;
  const extra = viewQuery(view);
  const query = { ...baseQuery, ...extra };

  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['orders', query],
    queryFn: () => {
      // `status` accepts several values: repeat the parameter for django-filter.
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(query)) {
        if (k === 'status')
          String(v)
            .split(',')
            .forEach((s) => params.append('status', s));
        else params.set(k, String(v));
      }
      return apiGet<Paginated<OrderList>>(`/api/v1/orders/?${params.toString()}`);
    },
    placeholderData: (previous) => previous,
    refetchInterval: 60_000,
  });

  return (
    <>
      <PageHeader
        title={t('Orders')}
        description={t('Quotations, confirmed work and deliveries.')}
        actions={
          <>
            <Can perm={Perm.REPORTS_ALL}>
              <Button
                variant="default"
                component={Link}
                to="/settings/import-export"
                leftSection={<IconFileSpreadsheet size={16} />}
              >
                {t('Excel import / export')}
              </Button>
            </Can>
            <Can perm={Perm.ORDERS_MANAGE}>
              <Button component={Link} to="/orders/new" leftSection={<IconPlus size={16} />}>
                {t('New order')}
              </Button>
            </Can>
          </>
        }
      />
      <Card padding={0}>
        <Stack gap="sm" p="md">
          <ScrollArea type="never">
            <SegmentedControl
              value={view}
              onChange={(v) => list.setFilter('view', v === 'all' ? null : v)}
              data={VIEWS.map((v) => ({ ...v, label: t(v.label) }))}
            />
          </ScrollArea>
          <TextInput
            placeholder={t('Search order no., customer, phone or description')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            aria-label={t('Search orders')}
          />
        </Stack>
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<OrderList>
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
            noRecordsText={t('No orders here')}
            onRowClick={({ record }) => navigate(`/orders/${record.id}`)}
            columns={[
              {
                accessor: 'order_no',
                title: t('Order'),
                render: (o) => (
                  <div>
                    <Group gap={6} wrap="nowrap">
                      <Anchor
                        component={Link}
                        to={`/orders/${o.id}`}
                        size="sm"
                        fw={500}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {o.order_no}
                      </Anchor>
                      {o.is_urgent && (
                        <Badge color="red" size="xs">
                          {t('Urgent')}
                        </Badge>
                      )}
                      {o.source === 'import' && (
                        <Badge color="slate" variant="outline" size="xs">
                          {t('Imported')}
                        </Badge>
                      )}
                    </Group>
                    <Text size="xs" c="dimmed">
                      {t('{{count}} items', { count: o.items_count })}
                      {o.invoice_no ? ` · ${o.invoice_no}` : ''}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'created_at',
                title: t('Date'),
                sortable: true,
                visibleMediaQuery: '(min-width: 48em)',
                render: (o) => <DualDate ad={o.order_date} bs={o.order_date_bs} />,
              },
              {
                accessor: 'customer',
                title: t('Customer'),
                render: (o) => (
                  <div>
                    <Text size="sm" lineClamp={1}>
                      {o.customer.name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {o.customer.phone}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'status',
                title: t('Status'),
                render: (o) => <StatusBadge value={o.status} map={ORDER_STATUS} />,
              },
              {
                accessor: 'deadline',
                title: t('Deliver by'),
                sortable: true,
                visibleMediaQuery: '(min-width: 62em)',
                render: (o) => {
                  const open = ['confirmed', 'in_production'].includes(o.status);
                  const late = open && o.deadline && new Date(o.deadline) < new Date();
                  return (
                    <Text size="sm" c={late ? 'red.7' : undefined}>
                      {o.deadline
                        ? open
                          ? deadlineLabel(o.deadline)
                          : new Date(o.deadline).toLocaleDateString('en-GB', {
                              day: 'numeric',
                              month: 'short',
                            })
                        : '—'}
                    </Text>
                  );
                },
              },
              {
                accessor: 'total',
                title: t('Total'),
                sortable: true,
                textAlign: 'right',
                render: (o) => <Money value={o.total} prefix={false} size="sm" />,
              },
              {
                accessor: 'balance_due',
                title: t('Balance'),
                textAlign: 'right',
                visibleMediaQuery: '(min-width: 36em)',
                render: (o) => <Money value={o.balance_due} prefix={false} tone="due" size="sm" />,
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
