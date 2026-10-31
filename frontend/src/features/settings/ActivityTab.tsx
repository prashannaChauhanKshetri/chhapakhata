import { Card, Group, Text, TextInput } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { DataTable } from '@/components/DataTable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDebouncedValue } from '@mantine/hooks';

import { apiGet } from '@/api/http';
import type { ActivityLog, Paginated } from '@/api/types';
import { formatDateTime } from '@/lib/format';

/** Who did what, and when: orders, payments, stock changes, cancellations, sign-ins. */
export function ActivityTab() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const query = { search: debounced, page, page_size: 30 };
  const { data, isFetching } = useQuery({
    queryKey: ['activity', query],
    queryFn: () => apiGet<Paginated<ActivityLog>>('/api/v1/activity/', query),
    placeholderData: (previous) => previous,
  });

  return (
    <Card padding={0}>
      <Group p="md">
        <TextInput
          placeholder={t('Search action, record or message')}
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value);
            setPage(1);
          }}
          style={{ flex: '1 1 260px' }}
          aria-label={t('Search activity')}
        />
      </Group>
      <DataTable<ActivityLog>
        minHeight={240}
        fetching={isFetching && !data}
        records={data?.results ?? []}
        totalRecords={data?.count ?? 0}
        recordsPerPage={30}
        page={page}
        onPageChange={setPage}
        noRecordsText={t('No activity recorded')}
        columns={[
          {
            accessor: 'created_at',
            title: t('When'),
            render: (a) => (
              <div>
                <Text size="sm">{formatDateTime(a.created_at)}</Text>
                <Text size="xs" c="dimmed">
                  {a.created_at_bs} BS
                </Text>
              </div>
            ),
          },
          {
            accessor: 'actor',
            title: t('Who'),
            render: (a) => a.actor?.full_name || a.actor?.username || t('System'),
          },
          {
            accessor: 'action',
            title: t('What'),
            render: (a) => (
              <div>
                <Text size="sm" ff="monospace">
                  {a.action}
                </Text>
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {[a.target_label, a.message].filter(Boolean).join(' · ')}
                </Text>
              </div>
            ),
          },
          {
            accessor: 'ip_address',
            title: t('Device IP'),
            visibleMediaQuery: '(min-width: 62em)',
            render: (a) => a.ip_address ?? '—',
          },
        ]}
      />
    </Card>
  );
}
