import { Badge, Button, Group, Menu, Paper, Stack, Text, Tooltip } from '@mantine/core';
import { IconArrowRight, IconChevronDown, IconCircleCheck, IconUser } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import type { Job } from '@/api/types';
import { deadlineLabel, formatQty } from '@/lib/format';
import { STAGES } from '@/lib/status';

import classes from './Board.module.css';
import { useJobMover } from './useJobMover';

interface JobCardProps {
  job: Job;
  onOpen: (job: Job) => void;
}

export function JobCard({ job, onOpen }: JobCardProps) {
  const { t } = useTranslation();
  const mover = useJobMover();
  const busy = mover.busyId === job.id;
  const next =
    job.allowed_stages.filter((s) => s > job.stage && s !== 6).sort((a, b) => a - b)[0] ??
    (job.allowed_stages.includes(6) && job.stage === 5 ? 6 : undefined);
  const others = job.allowed_stages.filter((s) => s !== next);

  const move = (toStage: number) => mover.move(job, toStage);

  const tone = job.is_overdue ? classes.overdue : job.is_due_today ? classes.dueToday : '';

  return (
    <Paper
      withBorder
      radius="md"
      p="sm"
      className={`${classes.card} ${tone}`}
      data-job={job.job_no}
    >
      <Stack gap={6}>
        <Group justify="space-between" wrap="nowrap" gap="xs">
          <Text
            component="button"
            type="button"
            className={classes.cardTitle}
            onClick={() => onOpen(job)}
            fw={600}
            size="sm"
          >
            {job.job_no}
          </Text>
          <Group gap={4} wrap="nowrap">
            {job.priority === 1 && (
              <Badge color="red" size="xs">
                {t('Urgent')}
              </Badge>
            )}
            {job.material_recorded && (
              <Tooltip label={t('Material recorded')}>
                <IconCircleCheck
                  size={16}
                  color="var(--mantine-color-green-7)"
                  aria-label={t('Material recorded')}
                />
              </Tooltip>
            )}
          </Group>
        </Group>
        <div>
          <Text size="sm" fw={500} lineClamp={1}>
            {job.customer_name}
          </Text>
          <Text size="xs" c="dimmed" lineClamp={2}>
            {job.item.media_name} ·{' '}
            {job.item.size_label
              ? `${job.item.size_label} × ${job.item.quantity} (${formatQty(job.item.total_sqft)} sq ft)`
              : t('{{n}} pcs', { n: job.item.quantity })}
            {job.item.description ? ` · ${job.item.description}` : ''}
          </Text>
          {(job.item.finishing || job.item.addons.length > 0) && (
            <Text size="xs" c="dimmed" lineClamp={1}>
              {[job.item.finishing, ...job.item.addons].filter(Boolean).join(', ')}
            </Text>
          )}
        </div>
        <Group justify="space-between" gap={4} wrap="nowrap">
          <Text
            size="xs"
            fw={500}
            c={job.is_overdue ? 'red.7' : job.is_due_today ? 'amber.8' : 'dimmed'}
            lineClamp={1}
          >
            {job.stage >= 5 ? job.order_no : deadlineLabel(job.deadline)}
          </Text>
          {job.operator && (
            <Group gap={2} wrap="nowrap">
              <IconUser size={12} color="var(--ck-text-muted)" />
              <Text size="xs" c="dimmed" lineClamp={1}>
                {job.operator.full_name || job.operator.username}
              </Text>
            </Group>
          )}
        </Group>
        {job.allowed_stages.length > 0 && (
          <Group gap={4} wrap="nowrap" className="no-print">
            {next !== undefined && (
              <Button
                size="compact-sm"
                variant="light"
                color="slate"
                rightSection={<IconArrowRight size={14} />}
                loading={busy}
                onClick={() => void move(next)}
                style={{ flex: 1 }}
              >
                {STAGES[next].short}
              </Button>
            )}
            {others.length > 0 && (
              <Menu position="bottom-end" withinPortal>
                <Menu.Target>
                  <Button
                    size="compact-sm"
                    variant="default"
                    px={6}
                    aria-label={t('Move to another stage')}
                    disabled={busy}
                  >
                    <IconChevronDown size={14} />
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>{t('Move to')}</Menu.Label>
                  {others.map((s) => (
                    <Menu.Item key={s} onClick={() => void move(s)}>
                      {STAGES[s].label}
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            )}
          </Group>
        )}
      </Stack>
    </Paper>
  );
}
