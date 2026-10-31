import { Alert, Button, Card, Group, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconCloudUpload, IconDatabase, IconDownload } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DataTable } from '@/components/DataTable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { BackupRun, Paginated } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { SectionCard } from '@/components/SectionCard';
import { StatusBadge } from '@/components/StatusBadge';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatBytes, formatDateTime } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { BACKUP_STATUS } from '@/lib/status';

export function BackupsTab() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const client = useQueryClient();
  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ['backups'],
    queryFn: () => apiGet<Paginated<BackupRun>>('/api/v1/system/backups/'),
    enabled: can(Perm.SYSTEM_BACKUP),
  });
  const runs = data?.results ?? [];
  const lastOk = runs.find((r) => r.status === 'success');

  const runNow = async () => {
    setRunning(true);
    try {
      const run = await unwrap(api.POST('/api/v1/system/backups/run/'));
      await client.invalidateQueries({ queryKey: ['backups'] });
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      if (run.status === 'success')
        notifySuccess(t('Backup finished ({{size}})', { size: formatBytes(run.size_bytes ?? 0) }));
      else notifyError(new Error(run.message || t('Backup failed')), t('Backup failed'));
    } catch (error) {
      notifyError(error, t('Backup failed'));
    } finally {
      setRunning(false);
    }
  };

  const exportAll = async () => {
    setExporting(true);
    try {
      await openFile('/api/v1/system/export/', { download: true });
    } catch (error) {
      notifyError(error, t('Export failed'));
    } finally {
      setExporting(false);
    }
  };

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        {can(Perm.SYSTEM_BACKUP) && (
          <Card>
            <Group gap="sm" align="flex-start" wrap="nowrap">
              <IconDatabase size={22} stroke={1.6} color="var(--ck-text-strong)" />
              <Stack gap={4} style={{ flex: 1 }}>
                <Text fw={600}>{t('Automatic backup')}</Text>
                <Text size="sm" c="dimmed">
                  {t(
                    'Runs every night on the shop computer. 14 daily, 8 weekly and 12 monthly copies are kept.',
                  )}
                </Text>
                <Text size="sm">
                  {lastOk
                    ? t('Last good backup: {{when}}', { when: formatDateTime(lastOk.started_at) })
                    : t('No backup yet.')}
                </Text>
                <Group gap={6}>
                  <IconCloudUpload size={16} color="var(--ck-text-muted)" />
                  <Text size="sm" c="dimmed">
                    {lastOk ? lastOk.offsite_status_label : '—'}
                  </Text>
                </Group>
                <Button mt="xs" w="fit-content" onClick={() => void runNow()} loading={running}>
                  {t('Back up now')}
                </Button>
              </Stack>
            </Group>
          </Card>
        )}
        {can(Perm.SETTINGS_MANAGE) && (
          <Card>
            <Group gap="sm" align="flex-start" wrap="nowrap">
              <IconDownload size={22} stroke={1.6} color="var(--ck-text-strong)" />
              <Stack gap={4} style={{ flex: 1 }}>
                <Text fw={600}>{t('Export all data')}</Text>
                <Text size="sm" c="dimmed">
                  {t(
                    'Download every table (customers, orders, invoices, payments, ledger, stock) as one Excel file. The data belongs to you.',
                  )}
                </Text>
                <Button
                  mt="xs"
                  variant="default"
                  w="fit-content"
                  onClick={() => void exportAll()}
                  loading={exporting}
                >
                  {t('Download Excel export')}
                </Button>
              </Stack>
            </Group>
          </Card>
        )}
      </SimpleGrid>

      {lastOk === undefined && !isPending && (
        <Alert color="amber">
          {t(
            'No successful backup is on record. Run one now and check the online copy settings with your developer.',
          )}
        </Alert>
      )}

      {can(Perm.SYSTEM_BACKUP) && (
        <SectionCard title={t('Backup history')} flush>
          <DataTable<BackupRun>
            minHeight={120}
            fetching={isPending}
            records={runs}
            noRecordsText={t('No backups yet')}
            columns={[
              {
                accessor: 'started_at',
                title: t('Started'),
                render: (r) => formatDateTime(r.started_at),
              },
              { accessor: 'trigger_label', title: t('Type') },
              {
                accessor: 'status',
                title: t('Status'),
                render: (r) => <StatusBadge value={r.status ?? 'running'} map={BACKUP_STATUS} />,
              },
              {
                accessor: 'size_bytes',
                title: t('Size'),
                textAlign: 'right',
                render: (r) => (r.size_bytes ? formatBytes(r.size_bytes) : '—'),
              },
              {
                accessor: 'offsite_status_label',
                title: t('Online copy'),
                visibleMediaQuery: '(min-width: 48em)',
                render: (r) => (
                  <div>
                    <Text size="sm">{r.offsite_status_label}</Text>
                    {r.offsite_message && (
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {r.offsite_message}
                      </Text>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </SectionCard>
      )}
    </Stack>
  );
}
