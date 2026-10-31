import { Button, Card, Group, Stack, Text, TextInput } from '@mantine/core';
import { IconSearch, IconTruckDelivery } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from '@/components/DataTable';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/http';
import type { Paginated, Purchase } from '@/api/types';
import { DualDate } from '@/components/DualDate';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { formatQty } from '@/lib/format';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

export default function PurchasesPage() {
  const { t } = useTranslation();
  const list = useListState([] as const, '-purchase_date');
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['purchases', list.query],
    queryFn: () => apiGet<Paginated<Purchase>>('/api/v1/purchases/', list.query),
    placeholderData: (previous) => previous,
  });

  return (
    <>
      <PageHeader
        title={t('Purchases')}
        description={t(
          'Stock received from suppliers. Each roll gets its own code for roll-wise tracking.',
        )}
        actions={
          <Button
            component={Link}
            to="/purchases/new"
            leftSection={<IconTruckDelivery size={16} />}
          >
            {t('Record purchase')}
          </Button>
        }
      />
      <Card padding={0}>
        <Group p="md">
          <TextInput
            placeholder={t('Purchase no., supplier or bill no.')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 260px' }}
            aria-label={t('Search purchases')}
          />
        </Group>
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<Purchase>
            minHeight={240}
            records={data?.results ?? []}
            fetching={isFetching && !data}
            totalRecords={data?.count ?? 0}
            recordsPerPage={PAGE_SIZE}
            page={list.page}
            onPageChange={list.setPage}
            noRecordsText={t('No purchases recorded yet')}
            rowExpansion={{
              content: ({ record }) => (
                <Stack gap={4} px="lg" py="sm" bg="slate.0">
                  {record.lines.map((line) => (
                    <Group key={line.id} justify="space-between">
                      <Text size="sm">
                        {line.stock_item_name}
                        {line.roll_count
                          ? ` · ${line.roll_count} × ${formatQty(line.roll_width_ft)} × ${formatQty(line.roll_length_ft)} ft rolls`
                          : ''}
                      </Text>
                      <Text size="sm" className="num">
                        {formatQty(line.quantity)} {line.unit} · Rs {formatQty(line.amount)}
                      </Text>
                    </Group>
                  ))}
                  {record.notes && (
                    <Text size="xs" c="dimmed">
                      {record.notes}
                    </Text>
                  )}
                </Stack>
              ),
            }}
            columns={[
              {
                accessor: 'purchase_no',
                title: t('Purchase'),
                render: (p) => (
                  <Text size="sm" fw={500}>
                    {p.purchase_no}
                  </Text>
                ),
              },
              {
                accessor: 'purchase_date',
                title: t('Date'),
                render: (p) => <DualDate ad={p.purchase_date} bs={p.purchase_date_bs} />,
              },
              { accessor: 'supplier_name', title: t('Supplier') },
              {
                accessor: 'bill_no',
                title: t('Bill no.'),
                visibleMediaQuery: '(min-width: 48em)',
                render: (p) => p.bill_no || '—',
              },
              {
                accessor: 'total_amount',
                title: t('Amount'),
                textAlign: 'right',
                render: (p) => <Money value={p.total_amount} prefix={false} size="sm" />,
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
