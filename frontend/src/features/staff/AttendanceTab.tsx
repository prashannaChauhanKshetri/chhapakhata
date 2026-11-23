import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  SegmentedControl,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core';
import {
  IconCalendarMonth,
  IconChevronLeft,
  IconChevronRight,
  IconLock,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { DateConversion, DayRegister, DayRow, DayStatus, Staff } from '@/api/types';
import { QueryError } from '@/components/QueryError';
import { notifyError } from '@/lib/forms';
import { formatDate, todayISO } from '@/lib/format';

import { OrderDateField } from '../orders/OrderDateField';
import { openAttendanceCalendar } from './AttendanceCalendar';
import { AttendanceRegister } from './AttendanceRegister';
import classes from './AttendanceTab.module.css';

const WEEKDAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Mark one day for everyone at the top; see and correct the whole month below. */
export function AttendanceTab() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [day, setDay] = useState(todayISO());
  const [saving, setSaving] = useState<string | null>(null);

  const dayKey = ['staff', 'attendance', day];
  const { data, error, refetch } = useQuery({
    queryKey: dayKey,
    queryFn: () => apiGet<DayRegister>('/api/v1/attendance/', { date: day }),
  });
  const { data: staffList } = useQuery({
    queryKey: ['staff', 'list'],
    queryFn: () => apiGet<Staff[]>('/api/v1/staff/'),
  });
  // Workers who join after the chosen day are not in its list; say so instead of hiding them.
  const upcoming = (staffList ?? []).filter((s) => s.is_active && s.joined_on > day);
  const { data: dayInfo } = useQuery({
    queryKey: ['date-conversion', 'ad', day],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/', { ad: day }),
    staleTime: Infinity,
  });
  const save = async (staffId: number, date: string, status: DayStatus) => {
    setSaving(`${staffId}:${date}`);
    try {
      await unwrap(api.POST('/api/v1/attendance/', { body: { staff: staffId, date, status } }));
    } catch (e) {
      notifyError(e, t('Could not mark attendance'));
    } finally {
      setSaving(null);
      // The day list, the register, the calendar and the month's pay all change.
      await client.invalidateQueries({ queryKey: ['staff'] });
    }
  };

  const markDay = (row: DayRow, status: DayStatus) => {
    client.setQueryData<DayRegister>(
      dayKey,
      (old) =>
        old && {
          ...old,
          rows: old.rows.map((r) => (r.staff.id === row.staff.id ? { ...r, status } : r)),
        },
    );
    void save(row.staff.id, day, status);
  };

  const holiday = data?.is_holiday ?? false;
  const rows = data?.rows ?? [];
  const absent = rows.filter((r) => r.status === 'absent').length;
  const worked = rows.filter((r) => r.status === 'worked').length;
  const today = todayISO();
  const weekday = new Date(`${day}T00:00:00`).getDay();

  return (
    <Stack gap="md">
      {/* -- The day ---------------------------------------------------------------- */}
      <Card>
        <Group justify="space-between" align="flex-start" gap="sm">
          <div>
            <Text size="sm" c={holiday ? 'red.7' : 'dimmed'} fw={600}>
              {t(WEEKDAY_NAMES[weekday])}
              {day === today ? ` · ${t('Today')}` : ''}
            </Text>
            <div className={classes.dayTitle}>{dayInfo?.bs_long ?? '…'}</div>
            <Text size="sm" c="dimmed">
              {formatDate(day)}
            </Text>
          </div>
          <Group gap={6} wrap="nowrap">
            <Tooltip label={t('Previous day')}>
              <ActionIcon
                variant="default"
                size={36}
                onClick={() => setDay(shiftDay(day, -1))}
                aria-label={t('Previous day')}
              >
                <IconChevronLeft size={18} />
              </ActionIcon>
            </Tooltip>
            <Button variant="default" disabled={day === today} onClick={() => setDay(today)}>
              {t('Today')}
            </Button>
            <Tooltip label={t('Next day')}>
              <ActionIcon
                variant="default"
                size={36}
                disabled={day >= today}
                onClick={() => setDay(shiftDay(day, 1))}
                aria-label={t('Next day')}
              >
                <IconChevronRight size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
        <div style={{ marginTop: 'var(--mantine-spacing-sm)' }}>
          <OrderDateField value={day} onChange={setDay} label={t('Day')} showHint={false} />
        </div>
      </Card>

      {error ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : data && rows.length === 0 ? (
        <Card>
          <Stack align="flex-start" gap="sm">
            <Text c="dimmed">{t('No staff working on this day.')}</Text>
            <Button component={Link} to="/staff/list" variant="default">
              {t('Add staff')}
            </Button>
          </Stack>
        </Card>
      ) : (
        <Card padding={0}>
          <Group justify="space-between" p="var(--ck-card-pad)" pb="sm" gap="sm">
            <div className={classes.counts}>
              {holiday ? (
                <>
                  <div className={classes.count}>
                    <strong>{rows.length - worked}</strong>
                    <span>{t('Off (Saturday)')}</span>
                  </div>
                  <div className={classes.count}>
                    <strong style={{ color: 'var(--mantine-color-blue-7)' }}>{worked}</strong>
                    <span>{t('Worked')}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className={classes.count}>
                    <strong>{rows.length - absent}</strong>
                    <span>{t('Present')}</span>
                  </div>
                  <div className={classes.count}>
                    <strong style={{ color: absent ? 'var(--mantine-color-red-7)' : undefined }}>
                      {absent}
                    </strong>
                    <span>{t('Absent')}</span>
                  </div>
                </>
              )}
            </div>
            <Text size="xs" c="dimmed" maw={260}>
              {holiday
                ? t('Saturday is the weekly holiday. Mark who came to work.')
                : t('Everyone counts as present. Mark only who is absent.')}
            </Text>
          </Group>
          <div className="ck-rows">
            {rows.map((row) => (
              <Group
                key={row.staff.id}
                className="ck-row"
                justify="space-between"
                wrap="nowrap"
                gap="sm"
              >
                <Group gap={4} wrap="nowrap" miw={0}>
                  <Tooltip label={t('Whole month')}>
                    <ActionIcon
                      onClick={() => openAttendanceCalendar(row.staff)}
                      aria-label={t('Month of {{name}}', { name: row.staff.name })}
                    >
                      <IconCalendarMonth size={18} />
                    </ActionIcon>
                  </Tooltip>
                  <div style={{ minWidth: 0 }}>
                    <Text fw={500} lineClamp={2} lh={1.25}>
                      {row.staff.name}
                    </Text>
                    {row.staff.job_title && (
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {row.staff.job_title}
                      </Text>
                    )}
                  </div>
                </Group>
                <Group gap={6} wrap="nowrap">
                  {row.locked && (
                    <Tooltip
                      label={t(
                        'Locked: this month is paid, or the day is covered by the opening balance.',
                      )}
                    >
                      <IconLock size={16} color="var(--mantine-color-slate-5)" />
                    </Tooltip>
                  )}
                  <SegmentedControl
                    disabled={row.locked || saving === `${row.staff.id}:${day}`}
                    value={row.status}
                    color={
                      row.status === 'absent' ? 'red' : row.status === 'worked' ? 'blue' : 'green'
                    }
                    onChange={(v) => markDay(row, v as DayStatus)}
                    data={
                      holiday
                        ? [
                            { value: 'off', label: t('Off') },
                            { value: 'worked', label: t('Worked') },
                          ]
                        : [
                            { value: 'present', label: t('Present') },
                            { value: 'absent', label: t('Absent') },
                          ]
                    }
                    aria-label={t('Attendance of {{name}}', { name: row.staff.name })}
                  />
                </Group>
              </Group>
            ))}
          </div>
        </Card>
      )}

      {upcoming.length > 0 && (
        <Alert color="amber" p="sm">
          <Text size="sm">
            {t('Not counted yet, because their joining date is after this day:')}{' '}
            {upcoming.map((s) => `${s.name} (${s.joined_on_bs} BS)`).join(', ')}.{' '}
            {t('If a date is wrong, correct it in')}{' '}
            <Anchor component={Link} to="/staff/list" size="sm">
              {t('Staff')}
            </Anchor>
            .
          </Text>
        </Alert>
      )}

      <AttendanceRegister pickedDay={day} onPickDay={setDay} />
    </Stack>
  );
}
