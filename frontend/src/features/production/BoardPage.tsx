import {
  Badge,
  Box,
  Card,
  Chip,
  Group,
  Loader,
  ScrollArea,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue, useMediaQuery } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { Board, Job } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { EmptyState } from '@/components/EmptyState';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { StageBadge } from '@/components/StatusBadge';

import { useMediaTypes } from '../orders/useCatalog';
import classes from './Board.module.css';
import { JobCard } from './JobCard';
import { JobDrawer } from './JobDrawer';

export default function BoardPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isPhone = useMediaQuery('(max-width: 48em)');
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 300);
  const [due, setDue] = useState<string>('all');
  const [media, setMedia] = useState<string | null>(null);
  const [mine, setMine] = useState(false);
  const [openJob, setOpenJob] = useState<number | null>(null);
  const [phoneStage, setPhoneStage] = useState('1');
  const [showDelivered, setShowDelivered] = useState(false);
  const { data: mediaTypes = [] } = useMediaTypes();

  const query = {
    search: debounced,
    due: due === 'all' ? undefined : due,
    media_type: media ?? undefined,
    mine: mine ? 'true' : undefined,
  };
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['board', query],
    queryFn: () => apiGet<Board>('/api/v1/jobs/board/', query),
    refetchInterval: 30_000,
    placeholderData: (previous) => previous,
  });

  const filters = (
    <Group gap="sm" wrap="wrap" mb="md">
      <TextInput
        placeholder={t('Job, order, customer or material')}
        leftSection={<IconSearch size={16} />}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        style={{ flex: '1 1 240px' }}
        aria-label={t('Search jobs')}
      />
      <SegmentedControl
        value={due}
        onChange={setDue}
        data={[
          { value: 'all', label: t('All') },
          { value: 'today', label: t('Due today') },
          { value: 'overdue', label: t('Overdue') },
        ]}
      />
      {mediaTypes.length > 0 && (
        <Select
          placeholder={t('All media')}
          clearable
          w={180}
          data={mediaTypes.map((m) => ({ value: String(m.id), label: m.name }))}
          value={media}
          onChange={setMedia}
          aria-label={t('Filter by media')}
        />
      )}
      {user?.role === 'operator' && (
        <Chip checked={mine} onChange={setMine} variant="outline">
          {t('My jobs')}
        </Chip>
      )}
      {data && (
        <Chip checked={showDelivered} onChange={setShowDelivered} variant="outline">
          {t('Delivered today ({{n}})', { n: data.columns.find((c) => c.stage === 6)?.count ?? 0 })}
        </Chip>
      )}
      {isFetching && <Loader size="xs" color="slate.4" />}
    </Group>
  );

  const renderCards = (jobs: Job[]) =>
    jobs.length === 0 ? (
      <Text size="sm" c="dimmed" ta="center" py="md">
        {t('No jobs')}
      </Text>
    ) : (
      jobs.map((job) => <JobCard key={job.id} job={job} onOpen={(j) => setOpenJob(j.id)} />)
    );

  return (
    <>
      <PageHeader
        title={t('Production board')}
        description={t('Every job by stage. Updates every 30 seconds.')}
        badge={
          data ? (
            <Group gap={6}>
              <Badge color="slate">{t('{{count}} open', { count: data.total_open })}</Badge>
              {data.overdue > 0 && (
                <Badge color="red">{t('{{count}} overdue', { count: data.overdue })}</Badge>
              )}
              {data.due_today > 0 && (
                <Badge color="amber">{t('{{count}} due today', { count: data.due_today })}</Badge>
              )}
            </Group>
          ) : undefined
        }
      />
      {filters}
      {error ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : !data ? (
        <Card>
          <Loader size="sm" />
        </Card>
      ) : data.total_open === 0 && data.columns.every((c) => c.count === 0) ? (
        <Card>
          <EmptyState
            title={t('No jobs on the board')}
            description={t('Confirmed orders create jobs here automatically.')}
          />
        </Card>
      ) : isPhone ? (
        <Stack gap="sm">
          <ScrollArea type="never">
            <SegmentedControl
              value={phoneStage}
              onChange={setPhoneStage}
              data={data.columns.map((c) => ({
                value: String(c.stage),
                label: `${c.label.split(' /')[0]} (${c.count})`,
              }))}
            />
          </ScrollArea>
          {renderCards(data.columns.find((c) => String(c.stage) === phoneStage)?.jobs ?? [])}
        </Stack>
      ) : (
        <Box
          className={classes.columns}
          style={{ '--board-columns': showDelivered ? 6 : 5 } as React.CSSProperties}
        >
          {data.columns
            .filter((column) => showDelivered || column.stage !== 6)
            .map((column) => (
              <section key={column.stage} className={classes.column} aria-label={column.label}>
                <Group justify="space-between" className={classes.columnHeader} wrap="nowrap">
                  <StageBadge stage={column.stage} />
                  <Text size="xs" fw={600} c="dimmed">
                    {column.count}
                  </Text>
                </Group>
                <div className={classes.columnBody}>{renderCards(column.jobs)}</div>
              </section>
            ))}
        </Box>
      )}
      <JobDrawer jobId={openJob} onClose={() => setOpenJob(null)} />
    </>
  );
}
