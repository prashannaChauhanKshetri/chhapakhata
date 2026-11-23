import { ActionIcon, Alert, Badge, Group, Stack, Text, Tooltip } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconChevronLeft, IconChevronRight, IconLock } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { components } from '@/api/schema';
import type { DayStatus } from '@/api/types';
import { QueryError } from '@/components/QueryError';
import { notifyError } from '@/lib/forms';

import classes from './AttendanceCalendar.module.css';

type StaffMonth = components['schemas']['StaffMonth'];
type MonthDay = components['schemas']['MonthDay'];

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MARK: Record<string, string> = {
  present: 'Present',
  absent: 'Absent',
  off: 'Off',
  worked: 'Worked',
  not_working: '',
};
/** A tap switches between the two states a day can have. */
const NEXT: Record<string, DayStatus> = {
  present: 'absent',
  absent: 'present',
  off: 'worked',
  worked: 'off',
};

const monthParam = (year: number, month: number) => `${year}-${String(month).padStart(2, '0')}`;

/** One worker's month: tap a past day to correct it. */
function AttendanceCalendar({ staffId, initialMonth }: { staffId: number; initialMonth?: string }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [month, setMonth] = useState<string | undefined>(initialMonth);
  const [saving, setSaving] = useState<string | null>(null);
  const key = ['staff', 'days', staffId, month];
  const { data, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () =>
      apiGet<StaffMonth>(`/api/v1/staff/${staffId}/days/`, month ? { month } : undefined),
  });

  const toggle = async (day: MonthDay) => {
    const status = NEXT[day.status];
    if (!status) return;
    setSaving(day.date);
    client.setQueryData<StaffMonth>(
      key,
      (old) =>
        old && { ...old, days: old.days.map((d) => (d.date === day.date ? { ...d, status } : d)) },
    );
    try {
      await unwrap(
        api.POST('/api/v1/attendance/', { body: { staff: staffId, date: day.date, status } }),
      );
      // The daily register and the month's pay change with it.
      await client.invalidateQueries({ queryKey: ['staff', 'attendance'] });
      await client.invalidateQueries({ queryKey: ['staff', 'salary'] });
    } catch (e) {
      notifyError(e, t('Could not change the day'));
      await refetch();
    } finally {
      setSaving(null);
    }
  };

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  const days = data?.days ?? [];
  const lead = days[0]?.weekday ?? 0;
  const absent = days.filter((d) => d.status === 'absent').length;
  const worked = days.filter((d) => d.status === 'worked').length;

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="nowrap">
        <Tooltip label={data?.previous.label}>
          <ActionIcon
            variant="default"
            size={36}
            disabled={!data}
            onClick={() => data && setMonth(monthParam(data.previous.year, data.previous.month))}
            aria-label={t('Previous month')}
          >
            <IconChevronLeft size={18} />
          </ActionIcon>
        </Tooltip>
        <Text fw={600} size="lg">
          {data?.label ?? '…'}
        </Text>
        <Tooltip label={data?.next?.label ?? t('Not started yet')}>
          <ActionIcon
            variant="default"
            size={36}
            disabled={!data?.next}
            onClick={() => data?.next && setMonth(monthParam(data.next.year, data.next.month))}
            aria-label={t('Next month')}
          >
            <IconChevronRight size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      {data?.paid && (
        <Alert color="slate" p="xs" icon={<IconLock size={16} />}>
          {t('This month is paid. Undo the payment on the Salary tab to change a day.')}
        </Alert>
      )}

      <div className={classes.grid} role="group" aria-label={data?.label}>
        {WEEKDAYS.map((w, i) => (
          <div key={w} className={clsx(classes.weekday, i === 6 && classes.weekend)}>
            {t(w)}
          </div>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <div key={`lead-${i}`} />
        ))}
        {days.map((d) => {
          const blank = d.status === 'not_working' || (!d.editable && !data?.paid);
          return (
            <button
              key={d.date}
              type="button"
              className={clsx(
                classes.day,
                blank ? classes.blank : classes[d.status],
                data?.paid && classes.locked,
              )}
              disabled={!d.editable || saving === d.date}
              onClick={() => void toggle(d)}
              aria-label={`${d.bs_day}: ${t(MARK[d.status] || 'Not working')}`}
            >
              <span className={classes.number}>{d.bs_day}</span>
              {!blank && <span className={classes.mark}>{t(MARK[d.status])}</span>}
            </button>
          );
        })}
      </div>

      <Group gap="xs">
        <Badge color={absent ? 'red' : 'green'}>{t('Absent: {{n}}', { n: absent })}</Badge>
        <Badge color="blue" variant={worked ? 'filled' : 'light'}>
          {t('Saturdays worked: {{n}}', { n: worked })}
        </Badge>
      </Group>
      <Text size="xs" c="dimmed">
        {t(
          'Tap a day to change it: a working day is present or absent; a Saturday is off or worked. Days still to come cannot be marked.',
        )}
      </Text>
    </Stack>
  );
}

export function openAttendanceCalendar(staff: { id: number; name: string }, month?: string) {
  modals.open({
    title: `${staff.name} · Attendance`,
    size: 'lg',
    children: <AttendanceCalendar staffId={staff.id} initialMonth={month} />,
  });
}
