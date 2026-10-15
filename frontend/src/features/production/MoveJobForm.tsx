import {
  Alert,
  Button,
  Group,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { Job, MaterialOptions } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatQty, toNumber } from '@/lib/format';
import { STAGES } from '@/lib/status';

export async function moveJob(jobId: number, toStage: number, extra: Record<string, unknown> = {}) {
  return unwrap(
    api.POST('/api/v1/jobs/{id}/move/', {
      params: { path: { id: jobId } },
      body: { to_stage: toStage as 1, ...extra },
    }),
  );
}

interface MoveJobFormProps {
  job: Job;
  toStage: number | null;
  onDone: () => void;
}

/** Record the roll and sq ft used (required when a job leaves Printing). */
export function MoveJobForm({ job, toStage, onDone }: MoveJobFormProps) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data: options, isPending } = useQuery({
    queryKey: ['jobs', job.id, 'material-options'],
    queryFn: () => apiGet<MaterialOptions>(`/api/v1/jobs/${job.id}/material-options/`),
  });

  const form = useForm({
    initialValues: {
      roll: '' as string,
      used_sqft: '' as number | string,
      wastage_sqft: 0 as number | string,
      wastage_reason: '',
      note: '',
    },
    validate: {
      roll: (v) => (v ? null : t('Choose the roll used')),
      used_sqft: (v) => (toNumber(v) > 0 ? null : t('Enter the sq ft used')),
    },
  });

  // Pre-fill once options arrive.
  if (options && form.values.used_sqft === '' && !form.isTouched('used_sqft')) {
    const fitting = options.rolls.find((r) => r.fits) ?? options.rolls[0];
    form.setValues({
      used_sqft: toNumber(options.default_used_sqft),
      roll: fitting ? String(fitting.id) : '',
    });
  }

  const finish = async () => {
    await Promise.all(
      ['board', 'jobs', 'order', 'orders', 'dashboard', 'stock-items', 'rolls'].map((k) =>
        client.invalidateQueries({ queryKey: [k] }),
      ),
    );
  };

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const material = {
        roll: Number(values.roll),
        used_sqft: String(values.used_sqft),
        wastage_sqft: String(toNumber(values.wastage_sqft)),
        wastage_reason: values.wastage_reason,
      };
      const result =
        toStage === null
          ? await unwrap(
              api.POST('/api/v1/jobs/{id}/record-material/', {
                params: { path: { id: job.id } },
                body: material,
              }),
            )
          : await moveJob(job.id, toStage, { material, note: values.note });
      await finish();
      notifySuccess(
        toStage === null
          ? t('Material recorded for {{job}}', { job: job.job_no })
          : t('{{job}} moved to {{stage}}', { job: job.job_no, stage: STAGES[toStage].short }),
      );
      result.warnings.forEach((w) => notifySuccess(w, t('Check')));
      onDone();
    } catch (error) {
      handleFormError(error, form, t('Not saved'));
    } finally {
      setBusy(false);
    }
  });

  const skip = async () => {
    if (toStage === null) return;
    setBusy(true);
    try {
      await moveJob(job.id, toStage, { skip_material: true, note: form.values.note });
      await finish();
      notifySuccess(t('{{job}} moved without recording material', { job: job.job_no }));
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  };

  const isOwner = user?.role === 'owner';
  const noRolls = options && options.rolls.length === 0;

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {job.item.media_name} · {job.item.size_label} × {job.item.quantity} ={' '}
          {formatQty(job.item.total_sqft)} sq ft
        </Text>
        {noRolls && (
          <Alert color="amber" icon={<IconAlertTriangle size={16} />}>
            {t('No {{material}} roll is in stock. Ask the owner to record the purchase first.', {
              material: options?.stock_item_name ?? t('matching'),
            })}
          </Alert>
        )}
        <Select
          label={t('Roll used')}
          placeholder={isPending ? t('Loading rolls…') : t('Choose roll')}
          data={(options?.rolls ?? []).map((r) => ({
            value: String(r.id),
            label: `${r.code} · ${formatQty(r.width_ft)} ft wide · ${formatQty(r.remaining_sqft)} sq ft left${r.fits ? '' : ' · too narrow'}`,
          }))}
          {...form.getInputProps('roll')}
        />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <NumberInput
            label={t('Sq ft used')}
            min={0}
            decimalScale={2}
            description={t('Printed area including bleed')}
            {...form.getInputProps('used_sqft')}
          />
          <NumberInput
            label={t('Wastage sq ft')}
            min={0}
            decimalScale={2}
            description={t('Misprints, test prints, trimming')}
            {...form.getInputProps('wastage_sqft')}
          />
        </SimpleGrid>
        {toNumber(form.values.wastage_sqft) > 0 && (
          <TextInput
            label={t('Wastage reason')}
            placeholder={t('e.g. Test print, head clog')}
            {...form.getInputProps('wastage_reason')}
          />
        )}
        {toStage !== null && (
          <Textarea label={t('Note (optional)')} minRows={1} {...form.getInputProps('note')} />
        )}
        <Group justify="space-between" mt="xs">
          {isOwner && toStage !== null ? (
            <Button variant="subtle" color="slate" onClick={() => void skip()} disabled={busy}>
              {t('Skip material')}
            </Button>
          ) : (
            <span />
          )}
          <Group gap="xs">
            <Button variant="default" onClick={onDone}>
              {t('Cancel')}
            </Button>
            <Button type="submit" loading={busy} disabled={noRolls}>
              {toStage === null ? t('Record material') : t('Save and move')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </form>
  );
}

export function openMoveJob(job: Job, toStage: number | null) {
  const id = modals.open({
    title:
      toStage === null ? `Material for ${job.job_no}` : `${job.job_no} → ${STAGES[toStage].short}`,
    size: 'lg',
    children: <MoveJobForm job={job} toStage={toStage} onDone={() => modals.close(id)} />,
  });
}

/** True when moving to `toStage` passes Printing and the job still needs material. */
export function needsMaterialForMove(job: Job, toStage: number): boolean {
  return job.needs_material && job.stage <= 3 && toStage > 3;
}
