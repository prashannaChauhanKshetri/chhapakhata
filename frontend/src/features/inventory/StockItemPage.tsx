import { Badge, Button, Menu, Progress, SimpleGrid, Stack, Text } from '@mantine/core';
import {
  IconAdjustments,
  IconChevronDown,
  IconPencil,
  IconPlus,
  IconRecycle,
  IconTool,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { Paginated, Roll, StockItem, StockMovement } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';
import { SectionCard } from '@/components/SectionCard';
import { StatCard } from '@/components/StatCard';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatDateTime, formatQty, toNumber } from '@/lib/format';
import { Perm } from '@/lib/permissions';

import { openOpeningStock, openStockAction, openStockItemModal } from './StockForms';

export default function StockItemPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const itemId = Number(id);
  const { can } = useAuth();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const {
    data: item,
    error,
    refetch,
  } = useQuery({
    queryKey: ['stock-items', itemId],
    queryFn: () => apiGet<StockItem>(`/api/v1/stock-items/${itemId}/`),
  });
  const { data: rolls } = useQuery({
    queryKey: ['rolls', { stock_item: itemId }],
    queryFn: () =>
      apiGet<Paginated<Roll>>('/api/v1/rolls/', {
        stock_item: itemId,
        page_size: 200,
        ordering: 'code',
      }),
    enabled: !!item?.is_roll_media,
  });
  const { data: movements, isFetching } = useQuery({
    queryKey: ['stock-movements', { stock_item: itemId, page }],
    queryFn: () =>
      apiGet<Paginated<StockMovement>>('/api/v1/stock-movements/', {
        stock_item: itemId,
        page,
        page_size: 25,
      }),
    placeholderData: (previous) => previous,
  });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  if (!item) return <PageLoader />;
  const rollList = rolls?.results ?? [];
  const activeRolls = rollList.filter((r) => r.status === 'active');

  const finishRoll = async (roll: Roll) => {
    try {
      await unwrap(
        api.POST('/api/v1/rolls/{id}/finish/', {
          params: { path: { id: roll.id } },
          body: { reason: 'Roll end written off' },
        }),
      );
      await Promise.all(
        ['rolls', 'stock-items', 'stock-movements'].map((k) =>
          client.invalidateQueries({ queryKey: [k] }),
        ),
      );
      notifySuccess(t('Roll {{code}} marked finished', { code: roll.code }));
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <>
      <PageHeader
        back={{ to: '/inventory', label: t('Inventory') }}
        title={item.name}
        badge={item.is_low ? <Badge color="red">{t('Low stock')}</Badge> : undefined}
        description={item.kind_label}
        actions={
          <>
            {can(Perm.INVENTORY_RECORD_USAGE) && (
              <Menu position="bottom-end">
                <Menu.Target>
                  <Button
                    variant="default"
                    rightSection={<IconChevronDown size={14} />}
                    leftSection={<IconTool size={16} />}
                  >
                    {t('Record')}
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item onClick={() => openStockAction(item, 'usage', rollList)}>
                    {t('Usage')}
                  </Menu.Item>
                  <Menu.Item onClick={() => openStockAction(item, 'wastage', rollList)}>
                    {t('Wastage')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
            {can(Perm.INVENTORY_MANAGE) && (
              <>
                <Button
                  variant="default"
                  leftSection={<IconAdjustments size={16} />}
                  onClick={() => openStockAction(item, 'adjust', rollList)}
                >
                  {t('Adjust after count')}
                </Button>
                <Button
                  variant="default"
                  leftSection={<IconPlus size={16} />}
                  onClick={() => openOpeningStock(item)}
                >
                  {t('Opening stock')}
                </Button>
                <Button
                  variant="default"
                  leftSection={<IconPencil size={16} />}
                  onClick={() => openStockItemModal(item)}
                >
                  {t('Edit')}
                </Button>
              </>
            )}
          </>
        }
      />
      <Stack gap="lg">
        <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="md">
          <StatCard
            label={t('On hand')}
            value={`${formatQty(item.on_hand)} ${item.unit_label}`}
            tone={item.is_low ? 'danger' : 'default'}
          />
          <StatCard
            label={t('Low-stock level')}
            value={
              toNumber(item.low_stock_level)
                ? `${formatQty(item.low_stock_level)} ${item.unit_label}`
                : t('Not set')
            }
          />
          {item.is_roll_media && (
            <StatCard
              label={t('Rolls in use')}
              value={activeRolls.length}
              hint={t('{{n}} finished', { n: rollList.length - activeRolls.length })}
            />
          )}
        </SimpleGrid>

        {item.is_roll_media && (
          <SectionCard title={t('Rolls')} flush>
            <DataTable<Roll>
              minHeight={120}
              records={rollList}
              noRecordsText={t('No rolls yet. Record a purchase or opening stock.')}
              rowStyle={(r) => (r.status === 'finished' ? { opacity: 0.6 } : undefined)}
              columns={[
                {
                  accessor: 'code',
                  title: t('Roll'),
                  render: (r) => (
                    <Text size="sm" fw={500}>
                      {r.code}
                    </Text>
                  ),
                },
                {
                  accessor: 'size',
                  title: t('Size'),
                  render: (r) => `${formatQty(r.width_ft)} × ${formatQty(r.length_ft)} ft`,
                },
                {
                  accessor: 'remaining_sqft',
                  title: t('Remaining'),
                  width: 240,
                  render: (r) => (
                    <Stack gap={2}>
                      <Text size="sm" className="num">
                        {formatQty(r.remaining_sqft)} / {formatQty(r.total_sqft)} sq ft
                      </Text>
                      <Progress
                        value={100 - toNumber(r.used_percent)}
                        color="slate.5"
                        size="sm"
                        radius="xl"
                        aria-hidden
                      />
                    </Stack>
                  ),
                },
                {
                  accessor: 'status',
                  title: t('Status'),
                  render: (r) => (
                    <Badge color={r.status === 'active' ? 'green' : 'slate'}>
                      {r.status_label}
                    </Badge>
                  ),
                },
                {
                  accessor: 'actions',
                  title: '',
                  textAlign: 'right',
                  render: (r) =>
                    can(Perm.INVENTORY_MANAGE) && r.status === 'active' ? (
                      <Button
                        size="compact-sm"
                        variant="subtle"
                        leftSection={<IconRecycle size={14} />}
                        onClick={() => void finishRoll(r)}
                      >
                        {t('Mark finished')}
                      </Button>
                    ) : null,
                },
              ]}
            />
          </SectionCard>
        )}

        <SectionCard title={t('Stock history')} flush>
          <DataTable<StockMovement>
            minHeight={200}
            fetching={isFetching && !movements}
            records={movements?.results ?? []}
            totalRecords={movements?.count ?? 0}
            recordsPerPage={25}
            page={page}
            onPageChange={setPage}
            noRecordsText={t('No stock movements yet')}
            columns={[
              {
                accessor: 'created_at',
                title: t('When'),
                render: (m) => (
                  <div>
                    <Text size="sm">{formatDateTime(m.created_at)}</Text>
                    <Text size="xs" c="dimmed">
                      {m.created_at_bs} BS
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'movement_type',
                title: t('Type'),
                render: (m) => (
                  <div>
                    <Text size="sm">{m.movement_type_label}</Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>
                      {[
                        m.roll_code,
                        m.job_no && !m.reason.includes(m.job_no) ? m.job_no : null,
                        m.reason,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'created_by',
                title: t('By'),
                visibleMediaQuery: '(min-width: 62em)',
                render: (m) => m.created_by.full_name || m.created_by.username,
              },
              {
                accessor: 'quantity',
                title: t('Change'),
                textAlign: 'right',
                render: (m) => (
                  <Text
                    size="sm"
                    className="num"
                    c={toNumber(m.quantity) < 0 ? 'slate.9' : 'green.8'}
                    fw={500}
                  >
                    {toNumber(m.quantity) > 0 ? '+' : ''}
                    {formatQty(m.quantity)}
                  </Text>
                ),
              },
              {
                accessor: 'balance_after',
                title: t('Balance'),
                textAlign: 'right',
                render: (m) => <span className="num">{formatQty(m.balance_after)}</span>,
              },
            ]}
          />
        </SectionCard>
      </Stack>
    </>
  );
}
