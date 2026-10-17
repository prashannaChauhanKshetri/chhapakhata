import { Button, Group, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Board, Job } from '@/api/types';
import { notifyError, notifySuccess } from '@/lib/forms';
import { STAGES } from '@/lib/status';

import { moveJob, needsMaterialForMove, openMoveJob } from './MoveJobForm';

/** Move a card to another column right away; the next refetch confirms it. */
function moveInBoard(board: Board, job: Job, toStage: number): Board {
  return {
    ...board,
    columns: board.columns.map((column) => {
      const jobs = column.jobs.filter((j) => j.id !== job.id);
      if (column.stage === toStage)
        jobs.unshift({ ...job, stage: toStage as Job['stage'], allowed_stages: [] });
      return { ...column, jobs, count: column.count + (jobs.length - column.jobs.length) };
    }),
  };
}

/**
 * The one way the board moves jobs, shared by the card buttons and drag-and-drop.
 * Moves past Printing open the material dialog first (operators must record usage).
 */
export function useJobMover() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busyId, setBusyId] = useState<number | null>(null);
  const undoSeq = useRef(0);

  const move = async (job: Job, toStage: number) => {
    if (needsMaterialForMove(job, toStage)) {
      openMoveJob(job, toStage);
      return;
    }
    setBusyId(job.id);
    await client.cancelQueries({ queryKey: ['board'] });
    client.setQueriesData<Board>({ queryKey: ['board'] }, (board) =>
      board ? moveInBoard(board, job, toStage) : board,
    );
    try {
      const result = await moveJob(job.id, toStage);
      const message = t('{{job}} moved to {{stage}}', {
        job: job.job_no,
        stage: STAGES[toStage].short,
      });
      // Easy reversal: offer to move it straight back, when this user may.
      if (
        result.job.allowed_stages.includes(job.stage) &&
        !needsMaterialForMove(result.job, job.stage)
      ) {
        undoSeq.current += 1;
        const id = `moved-${job.id}-${undoSeq.current}`;
        notifications.show({
          id,
          color: 'green',
          autoClose: 6000,
          message: (
            <Group justify="space-between" gap="sm" wrap="nowrap">
              <Text size="sm">{message}</Text>
              <Button
                size="compact-xs"
                variant="default"
                onClick={() => {
                  notifications.hide(id);
                  void move(result.job, job.stage);
                }}
              >
                {t('Undo')}
              </Button>
            </Group>
          ),
        });
      } else {
        notifySuccess(message);
      }
    } catch (error) {
      notifyError(error, t('Could not move {{job}}', { job: job.job_no }));
    } finally {
      // Refetch either way: confirms the move, or puts the card back after an error.
      await Promise.all(
        ['board', 'jobs', 'order', 'orders', 'dashboard'].map((k) =>
          client.invalidateQueries({ queryKey: [k] }),
        ),
      );
      setBusyId(null);
    }
  };

  return { move, busyId };
}
