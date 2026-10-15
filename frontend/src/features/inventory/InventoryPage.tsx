import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Progress,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconPlus, IconSearch, IconTruckDelivery } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { apiGet } from '@/api/http';
import type { StockItem } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { formatQty, toNumber } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { useListState } from '@/lib/useListState';

import { openStockItemModal } from './StockForms';

export default function InventoryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const list = useListState(['low', 'kind'] as const);
  const query = {
    search: list.debouncedSearch,
    low: list.filters.low || undefined,
    kind: list.filters.kind || undefined,
    is_active: 'true',
  };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['stock-items', query],
    queryFn: () => apiGet<StockItem[]>('/api/v1/stock-items/', query),
    placeholderData: (previous) => previous,
  });
  const lowCount = data?.filter((i) => i.is_low).length ?? 0;

  return (
    <>
      <PageHeader
        title={t('Inventory')}
        description={t(
          'Roll-wise media and other materials. Stock changes only through purchases, usage and counted adjustments.',
        )}
        actions={
          can(Perm.INVENTORY_MANAGE) && (
            <>
              <Button
                variant="default"
                leftSection={<IconPlus size={16} />}
                onClick={() => openStockItemModal()}
              >
                {t('New item')}
              </Button>
              <Button
                component={Link}
                to="/purchases/new"
                leftSection={<IconTruckDelivery size={16} />}
              >
                {t('Record purchase')}
              </Button>
            </>
          )
        }
      />
      <Card padding={0}>
        <Group p="md" gap="sm" wrap="wrap">
          <TextInput
            placeholder={t('Search stock items')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 240px' }}
            aria-label={t('Search stock items')}
          />
          <SegmentedControl
            value={list.filters.low === 'true' ? 'low' : 'all'}
            onChange={(v) => list.setFilter('low', v === 'low' ? 'true' : null)}
            data={[
              { value: 'all', label: t('All items') },
              {
                value: 'low',
                label: lowCount ? t('Low stock ({{n}})', { n: lowCount }) : t('Low stock'),
              },
            ]}
          />
        </Group>
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<StockItem>
            minHeight={240}
            highlightOnHover
            fetching={isFetching && !data}
            records={data ?? []}
            noRecordsText={t('No stock items yet')}
            onRowClick={({ record }) => navigate(`/inventory/${record.id}`)}
            columns={[
              {
                accessor: 'name',
                title: t('Item'),
                render: (i) => (
                  <div>
                    <Anchor
                      component={Link}
                      to={`/inventory/${i.id}`}
                      size="sm"
                      fw={500}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {i.name}
                    </Anchor>
                    <Text size="xs" c="dimmed">
                      {i.kind_label}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'active_rolls',
                title: t('Rolls'),
                visibleMediaQuery: '(min-width: 48em)',
                render: (i) =>
                  i.is_roll_media ? t('{{n}} in use', { n: i.active_rolls ?? 0 }) : '—',
              },
              {
                accessor: 'on_hand',
                title: t('On hand'),
                textAlign: 'right',
                render: (i) => (
                  <Text size="sm" className="num" fw={500} c={i.is_low ? 'red.7' : undefined}>
                    {formatQty(i.on_hand)} {i.unit_label}
                  </Text>
                ),
              },
              {
                accessor: 'low_stock_level',
                title: t('Level'),
                width: 200,
                visibleMediaQuery: '(min-width: 62em)',
                render: (i) => {
                  const level = toNumber(i.low_stock_level);
                  if (!level)
                    return (
                      <Text size="xs" c="dimmed">
                        {t('No alert set')}
                      </Text>
                    );
                  const pct = Math.min(100, (toNumber(i.on_hand) / (level * 3)) * 100);
                  return (
                    <Stack gap={2}>
                      <Progress
                        value={pct}
                        color={i.is_low ? 'red.6' : 'slate.5'}
                        size="sm"
                        radius="xl"
                        aria-hidden
                      />
                      <Text size="xs" c="dimmed">
                        {t('Alert below {{level}}', { level: formatQty(level) })}
                      </Text>
                    </Stack>
                  );
                },
              },
              {
                accessor: 'is_low',
                title: t('Status'),
                render: (i) =>
                  i.is_low ? (
                    <Badge color="red">{t('Low')}</Badge>
                  ) : (
                    <Badge color="green">{t('OK')}</Badge>
                  ),
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
