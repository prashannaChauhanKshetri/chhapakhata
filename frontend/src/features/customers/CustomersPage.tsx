import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconSearch, IconUserPlus } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from '@/components/DataTable';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { apiGet } from '@/api/http';
import type { Customer, Paginated } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Can } from '@/auth/Can';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { Perm } from '@/lib/permissions';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

import { openCustomerModal } from './CustomerForm';

export default function CustomersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const canAdd = can(Perm.CUSTOMERS_MANAGE);
  const list = useListState(['has_due', 'is_active'] as const, 'name');
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['customers', list.query],
    queryFn: () => apiGet<Paginated<Customer>>('/api/v1/customers/', list.query),
    placeholderData: (previous) => previous,
  });

  return (
    <>
      <PageHeader
        title={t('Customers')}
        description={t('Contacts, balances and statements.')}
        actions={
          <Can perm={Perm.CUSTOMERS_MANAGE}>
            <Button
              leftSection={<IconUserPlus size={16} />}
              onClick={() => openCustomerModal({ onSaved: (c) => navigate(`/customers/${c.id}`) })}
            >
              {t('New customer')}
            </Button>
          </Can>
        }
      />
      <Card padding={0}>
        <Group p="md" gap="sm" wrap="wrap">
          <TextInput
            placeholder={t('Search name, phone, PAN or address')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 260px' }}
            aria-label={t('Search customers')}
          />
          <SegmentedControl
            value={list.filters.has_due || 'all'}
            onChange={(v) => list.setFilter('has_due', v === 'all' ? null : v)}
            data={[
              { value: 'all', label: t('All') },
              { value: 'true', label: t('With dues') },
            ]}
          />
        </Group>
        {canAdd && data?.count === 0 && list.debouncedSearch.trim().length >= 2 && (
          <Alert
            mx="md"
            mb="md"
            color="slate"
            variant="light"
            title={t('No customer called “{{name}}”', { name: list.debouncedSearch.trim() })}
          >
            <Group justify="space-between" gap="sm">
              <Text size="sm">{t('Add them now. Only the name is needed; PAN is optional.')}</Text>
              <Button
                size="xs"
                leftSection={<IconUserPlus size={14} />}
                onClick={() =>
                  openCustomerModal({
                    initialName: list.debouncedSearch.trim(),
                    onSaved: (c) => navigate(`/customers/${c.id}`),
                  })
                }
              >
                {t('Add “{{name}}”', { name: list.debouncedSearch.trim() })}
              </Button>
            </Group>
          </Alert>
        )}
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<Customer>
            minHeight={240}
            highlightOnHover
            verticalSpacing="sm"
            records={data?.results ?? []}
            fetching={isFetching && !data}
            totalRecords={data?.count ?? 0}
            recordsPerPage={PAGE_SIZE}
            page={list.page}
            onPageChange={list.setPage}
            sortStatus={list.sortStatus as never}
            onSortStatusChange={list.setSort as never}
            noRecordsText={
              list.search ? t('No customer matches your search') : t('No customers yet')
            }
            onRowClick={({ record }) => navigate(`/customers/${record.id}`)}
            columns={[
              {
                accessor: 'name',
                title: t('Name'),
                sortable: true,
                render: (c) => (
                  <div>
                    <Anchor
                      component={Link}
                      to={`/customers/${c.id}`}
                      fw={500}
                      size="sm"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {c.name}
                    </Anchor>
                    {!c.is_active && (
                      <Text span size="xs" c="dimmed" ml={6}>
                        ({t('inactive')})
                      </Text>
                    )}
                    <Text size="xs" c="dimmed">
                      {c.customer_type_label}
                    </Text>
                  </div>
                ),
              },
              { accessor: 'phone', title: t('Phone'), render: (c) => c.phone || '—' },
              {
                accessor: 'address',
                title: t('Address'),
                visibleMediaQuery: '(min-width: 62em)',
                render: (c) => c.address || '—',
              },
              {
                accessor: 'pan_no',
                title: t('PAN'),
                visibleMediaQuery: '(min-width: 75em)',
                render: (c) => c.pan_no || '—',
              },
              {
                accessor: 'ledger_balance',
                title: t('Balance'),
                sortable: true,
                textAlign: 'right',
                render: (c) => <Money value={c.balance} tone="due" size="sm" />,
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
