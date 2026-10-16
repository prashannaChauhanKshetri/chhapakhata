import {
  Anchor,
  Badge,
  Button,
  Divider,
  Drawer,
  Group,
  Select,
  Stack,
  Text,
  Textarea,
  Timeline,
} from '@mantine/core';
import { IconPrinter, IconRuler } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { JobDetail, User } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { KeyValue } from '@/components/KeyValue';
import { StageBadge } from '@/components/StatusBadge';
import { notifyError, notifySuccess } from '@/lib/forms';
import { deadlineLabel, formatDateTime, formatQty } from '@/lib/format';
import { Perm } from '@/lib/permissions';

import { openMoveJob } from './MoveJobForm';

/** Keyed by job and saved notes, so it resets when another job opens. */
function NotesEditor({ initial, onSave }: { initial: string; onSave: (notes: string) => void }) {
  const { t } = useTranslation();
  const [notes, setNotes] = useState(initial);
  return (
    <Textarea
      label={t('Notes for production')}
      value={notes}
      onChange={(e) => setNotes(e.currentTarget.value)}
      onBlur={() => notes !== initial && onSave(notes)}
    />
  );
}

export function JobDrawer({ jobId, onClose }: { jobId: number | null; onClose: () => void }) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const client = useQueryClient();
  const { data: job } = useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => apiGet<JobDetail>(`/api/v1/jobs/${jobId}/`),
    enabled: jobId !== null,
  });
  const { data: operators = [] } = useQuery({
    queryKey: ['users', 'operators'],
    queryFn: () => apiGet<User[]>('/api/v1/users/operators/'),
    enabled: jobId !== null && can(Perm.PRODUCTION_MOVE),
    staleTime: 5 * 60_000,
  });

  const update = async (body: { operator?: number | null; notes?: string; priority?: 0 | 1 }) => {
    if (!job) return;
    try {
      await unwrap(api.PATCH('/api/v1/jobs/{id}/', { params: { path: { id: job.id } }, body }));
      await Promise.all(['jobs', 'board'].map((k) => client.invalidateQueries({ queryKey: [k] })));
      notifySuccess(t('Job updated'));
    } catch (error) {
      notifyError(error);
    }
  };

  return (
    <Drawer
      opened={jobId !== null}
      onClose={onClose}
      position="right"
      size="md"
      title={job ? job.job_no : t('Job')}
    >
      {job && (
        <Stack gap="md">
          <Group justify="space-between">
            <StageBadge stage={job.stage} full />
            {job.priority === 1 && <Badge color="red">{t('Urgent')}</Badge>}
          </Group>
          <KeyValue
            labelWidth={110}
            items={[
              {
                label: t('Order'),
                value: can(Perm.ORDERS_VIEW) ? (
                  <Anchor component={Link} to={`/orders/${job.order_id}`} size="sm">
                    {job.order_no}
                  </Anchor>
                ) : (
                  job.order_no
                ),
              },
              { label: t('Customer'), value: `${job.customer_name} · ${job.customer_phone}` },
              {
                label: t('Material'),
                value: `${job.item.media_name}${job.item.description ? ` · ${job.item.description}` : ''}`,
              },
              {
                label: t('Size'),
                value: job.item.size_label
                  ? `${job.item.size_label} × ${job.item.quantity} = ${formatQty(job.item.total_sqft)} sq ft`
                  : `${job.item.quantity} pcs`,
              },
              { label: t('Finishing'), value: job.item.finishing || '—' },
              { label: t('Add-ons'), value: job.item.addons.join(', ') || '—' },
              { label: t('Design file'), value: job.design_file_ref || '—' },
              {
                label: t('Deliver by'),
                value: job.deadline
                  ? `${formatDateTime(job.deadline)} (${deadlineLabel(job.deadline)})`
                  : '—',
              },
            ]}
          />
          <Group gap="xs">
            <Button
              variant="default"
              leftSection={<IconPrinter size={16} />}
              onClick={() =>
                void openFile(`/api/v1/jobs/${job.id}/ticket/`).catch((e) => notifyError(e))
              }
            >
              {t('Job ticket')}
            </Button>
            {can(Perm.INVENTORY_RECORD_USAGE) && job.item && (
              <Button
                variant="default"
                leftSection={<IconRuler size={16} />}
                onClick={() => openMoveJob(job, null)}
              >
                {job.material_recorded ? t('Record more material') : t('Record material')}
              </Button>
            )}
          </Group>

          {can(Perm.PRODUCTION_MOVE) && (
            <>
              <Divider />
              <Select
                label={t('Operator')}
                placeholder={t('Not assigned')}
                clearable
                data={operators.map((o) => ({
                  value: String(o.id),
                  label: o.full_name || o.username,
                }))}
                value={job.operator ? String(job.operator.id) : null}
                onChange={(v) => void update({ operator: v ? Number(v) : null })}
              />
              <NotesEditor
                key={`${job.id}-${job.notes}`}
                initial={job.notes ?? ''}
                onSave={(notes) => void update({ notes })}
              />
            </>
          )}

          {job.movements.length > 0 && (
            <>
              <Divider label={t('Material used')} labelPosition="left" />
              <Stack gap={4}>
                {job.movements.map((m) => (
                  <Group key={m.id} justify="space-between">
                    <Text size="sm">
                      {m.movement_type_label}
                      {m.roll_code ? ` · ${m.roll_code}` : ''}
                    </Text>
                    <Text size="sm" className="num">
                      {formatQty(Math.abs(Number(m.quantity)))} sq ft
                    </Text>
                  </Group>
                ))}
              </Stack>
            </>
          )}

          <Divider label={t('History')} labelPosition="left" />
          <Timeline bulletSize={12} lineWidth={2} color="slate">
            {job.events.map((e) => (
              <Timeline.Item key={e.id} title={<Text size="sm">{e.to_label}</Text>}>
                <Text size="xs" c="dimmed">
                  {formatDateTime(e.created_at)} ·{' '}
                  {e.created_by?.full_name || e.created_by?.username || '—'}
                </Text>
                {e.note && <Text size="xs">{e.note}</Text>}
              </Timeline.Item>
            ))}
          </Timeline>
        </Stack>
      )}
    </Drawer>
  );
}
