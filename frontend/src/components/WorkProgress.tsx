import { Box, Group, Progress, Text, Tooltip } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { OrderProgress } from '@/api/types';
import { BOARD_STAGES, STAGES } from '@/lib/status';

function tone(p: OrderProgress): string {
  if (p.percent >= 100) return 'green.6';
  if (p.jobs > 0 && p.jobs_ready === p.jobs) return 'green.6';
  return 'orange.6';
}

/**
 * How far an order has got in production. The bar is the average over all its
 * items; the label names the stage of the item furthest behind, which is what
 * the customer is waiting for.
 */
export function WorkProgress({ progress }: { progress: OrderProgress | null | undefined }) {
  const { t } = useTranslation();
  if (!progress) {
    return (
      <Text size="xs" c="dimmed">
        —
      </Text>
    );
  }
  const done = progress.percent >= 100;
  const caption = done
    ? t('Delivered')
    : progress.jobs > 1
      ? t('{{stage}} · {{ready}} of {{total}} ready', {
          stage: STAGES[progress.stage]?.short ?? progress.stage_label,
          ready: progress.jobs_ready,
          total: progress.jobs,
        })
      : (STAGES[progress.stage]?.short ?? progress.stage_label);
  return (
    <Tooltip label={`${progress.percent}% · ${progress.stage_label}`} openDelay={400}>
      <Box miw={120} maw={180}>
        <Progress
          value={progress.percent}
          color={tone(progress)}
          size="sm"
          radius="xl"
          bg="slate.1"
          aria-label={t('Production progress')}
        />
        <Text size="xs" c="dimmed" mt={4} lineClamp={1}>
          {caption}
        </Text>
      </Box>
    </Tooltip>
  );
}

/** The six production steps with the current one highlighted (order page). */
export function WorkSteps({ progress }: { progress: OrderProgress }) {
  const { t } = useTranslation();
  const color = tone(progress);
  return (
    <Box>
      <Group justify="space-between" mb={6}>
        <Text size="sm" fw={600}>
          {t('Production progress')}
        </Text>
        <Text size="sm" c="dimmed" className="num">
          {progress.percent}%
          {progress.jobs > 1 &&
            ` · ${t('{{ready}} of {{total}} items ready', {
              ready: progress.jobs_ready,
              total: progress.jobs,
            })}`}
        </Text>
      </Group>
      <Progress value={progress.percent} color={color} size="md" radius="xl" bg="slate.1" />
      <Group justify="space-between" mt={8} wrap="nowrap" gap={4} role="list">
        {BOARD_STAGES.map((stage) => {
          const reached = stage <= progress.stage;
          const current = stage === progress.stage && progress.percent < 100;
          return (
            <Text
              key={stage}
              role="listitem"
              size="xs"
              fw={current ? 600 : 400}
              c={current ? 'slate.9' : reached ? 'slate.6' : 'slate.4'}
              ta="center"
              style={{ flex: 1 }}
              aria-current={current ? 'step' : undefined}
            >
              {STAGES[stage].short}
            </Text>
          );
        })}
      </Group>
    </Box>
  );
}
