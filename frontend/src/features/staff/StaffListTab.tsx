import { Badge, Button, Card, Group, Text } from '@mantine/core';
import { IconUserPlus } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { Staff } from '@/api/types';
import { DataTable } from '@/components/DataTable';
import { Money } from '@/components/Money';
import { QueryError } from '@/components/QueryError';

import { openStaffForm } from './StaffForms';

/** Everyone on the payroll. Tap a row to change the salary or record that someone left. */
export function StaffListTab() {
  const { t } = useTranslation();
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: ['staff', 'list'],
    queryFn: () => apiGet<Staff[]>('/api/v1/staff/'),
  });
  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;

  return (
    <Card padding={0}>
      <Group justify="space-between" p="md" gap="sm">
        <Text size="sm" c="dimmed">
          {t('Staff need no login. Only the owner sees salaries.')}
        </Text>
        <Button leftSection={<IconUserPlus size={16} />} onClick={() => openStaffForm()}>
          {t('Add staff')}
        </Button>
      </Group>
      <DataTable<Staff>
        minHeight={160}
        highlightOnHover
        records={data ?? []}
        fetching={isFetching && !data}
        noRecordsText={t('No staff yet')}
        onRowClick={({ record }) => openStaffForm(record)}
        rowStyle={(s) => (!s.is_active ? { opacity: 0.6 } : undefined)}
        columns={[
          {
            accessor: 'name',
            title: t('Name'),
            render: (s) => (
              <div>
                <Text size="sm" fw={500}>
                  {s.name}
                </Text>
                {s.job_title && (
                  <Text size="xs" c="dimmed">
                    {s.job_title}
                  </Text>
                )}
              </div>
            ),
          },
          { accessor: 'phone', title: t('Phone'), render: (s) => s.phone || '—' },
          {
            accessor: 'joined_on',
            title: t('Joined'),
            render: (s) => `${s.joined_on_bs} BS`,
          },
          {
            accessor: 'is_active',
            title: t('Status'),
            render: (s) =>
              s.is_active ? (
                <Badge color="green">{t('Working')}</Badge>
              ) : (
                <Badge color="slate">{t('Left on {{date}}', { date: s.left_on_bs })}</Badge>
              ),
          },
          {
            accessor: 'saturday_pay',
            title: t('Saturday pay'),
            render: (s) =>
              s.saturday_pay != null ? (
                <Money value={s.saturday_pay} size="sm" />
              ) : (
                <Text size="sm" c="dimmed">
                  {t('One day')}
                </Text>
              ),
          },
          {
            accessor: 'monthly_salary',
            title: t('Monthly salary'),
            textAlign: 'right',
            render: (s) => <Money value={s.monthly_salary} size="sm" fw={500} />,
          },
        ]}
      />
    </Card>
  );
}
