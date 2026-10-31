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
import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { useDebouncedValue, useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { Board, BoardColumn, Job } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { EmptyState } from '@/components/EmptyState';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { StageBadge } from '@/components/StatusBadge';
import { BoardSkeleton } from '@/components/Skeletons';
import { STAGES } from '@/lib/status';

import { useMediaTypes } from '../orders/useCatalog';
import classes from './Board.module.css';
import { JobCard } from './JobCard';
import { JobDrawer } from './JobDrawer';
import { useJobMover } from './useJobMover';

/** A card that can be picked up, when the user may move it anywhere. */
function DraggableJob({ job, onOpen }: { job: Job; onOpen: (job: Job) => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: job.id,
    data: { job },
    disabled: job.allowed_stages.length === 0,
  });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={classes.draggable}
      data-dragging={isDragging || undefined}
      data-locked={job.allowed_stages.length === 0 || undefined}
    >
      <JobCard job={job} onOpen={onOpen} />
    </div>
  );
}

function StageColumn({
  column,
  dragging,
  children,
}: {
  column: BoardColumn;
  dragging: Job | null;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.stage, data: { stage: column.stage } });
  const home = dragging?.stage === column.stage;
  const allowed = !!dragging && dragging.allowed_stages.includes(column.stage);
  const state = !dragging || home ? undefined : allowed ? (isOver ? 'over' : 'open') : 'closed';
  return (
    <section
      ref={setNodeRef}
      className={classes.column}
      data-drop={state}
      aria-label={column.label}
    >
      <Group justify="space-between" className={classes.columnHeader} wrap="nowrap">
        <StageBadge stage={column.stage} />
        <Text size="xs" fw={600} c="dimmed">
          {column.count}
        </Text>
      </Group>
      <div className={classes.columnBody}>{children}</div>
    </section>
  );
}

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
  const mover = useJobMover();
  const [dragging, setDragging] = useState<Job | null>(null);
  // A short move (or a press on touch screens) starts a drag, so taps and buttons still work.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const onDragStart = (event: DragStartEvent) =>
    setDragging((event.active.data.current?.job as Job | undefined) ?? null);
  const onDragEnd = (event: DragEndEvent) => {
    setDragging(null);
    const job = event.active.data.current?.job as Job | undefined;
    const stage = event.over?.data.current?.stage as number | undefined;
    if (!job || stage === undefined || stage === job.stage) return;
    if (!job.allowed_stages.includes(stage)) {
      notifications.show({
        color: 'amber',
        title: t('{{job}} cannot move to {{stage}}', {
          job: job.job_no,
          stage: STAGES[stage].short,
        }),
        message:
          job.allowed_stages.length > 0
            ? t('From here it can go to: {{stages}}.', {
                stages: job.allowed_stages.map((s) => STAGES[s].short).join(', '),
              })
            : t('Your role cannot move this job at its current stage.'),
      });
      return;
    }
    void mover.move(job, stage);
  };

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
      {isFetching && data && <Loader size="xs" color="slate.4" />}
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
        description={
          isPhone
            ? t('Pick a stage, then move jobs with the buttons on each card.')
            : t('Drag a card to another stage, or use its buttons. Updates every 30 seconds.')
        }
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
        <BoardSkeleton />
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
        <DndContext
          sensors={sensors}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
          onDragCancel={() => setDragging(null)}
          accessibility={{
            screenReaderInstructions: {
              draggable: t(
                'To move a job, press space, use the arrow keys to choose a stage, then press space again.',
              ),
            },
          }}
        >
          <Box
            className={classes.columns}
            style={{ '--board-columns': showDelivered ? 6 : 5 } as React.CSSProperties}
          >
            {data.columns
              .filter((column) => showDelivered || column.stage !== 6)
              .map((column) => (
                <StageColumn key={column.stage} column={column} dragging={dragging}>
                  {column.jobs.length === 0 ? (
                    <Text size="sm" c="dimmed" ta="center" py="md">
                      {t('No jobs')}
                    </Text>
                  ) : (
                    column.jobs.map((job) => (
                      <DraggableJob key={job.id} job={job} onOpen={(j) => setOpenJob(j.id)} />
                    ))
                  )}
                </StageColumn>
              ))}
          </Box>
          <DragOverlay dropAnimation={null}>
            {dragging ? (
              <div className={classes.overlay}>
                <JobCard job={dragging} onOpen={() => undefined} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
      <JobDrawer jobId={openJob} onClose={() => setOpenJob(null)} />
    </>
  );
}
