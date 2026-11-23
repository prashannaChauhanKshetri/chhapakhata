import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  ScrollArea,
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
import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { components } from '@/api/schema';
import type { DateConversion, DayRegister, DayRow, DayStatus } from '@/api/types';
import { QueryError } from '@/components/QueryError';
import { notifyError } from '@/lib/forms';
import { formatDate, todayISO } from '@/lib/format';

import { OrderDateField } from '../orders/OrderDateField';
import { openAttendanceCalendar } from './AttendanceCalendar';
import classes from './AttendanceTab.module.css';

type MonthRegister = components['schemas']['MonthRegister'];

const WEEKDAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];
const WEEKDAY_LETTERS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
/** What a box in the register shows. */
const LETTER: Record<string, string> = {
  present: 'P',
  absent: 'A',
  worked: 'W',
  settled: '·',
  off: '',
  not_working: '',
};
const STATUS_NAME: Record<string, string> = {
  present: 'Present',
  absent: 'Absent',
  worked: 'Worked',
  off: 'Off',
  settled: 'Before the opening balance',
  not_working: 'Not working here',
};
/** A tap switches between the two states a day can have. */
const NEXT: Record<string, DayStatus> = {
  present: 'absent',
  absent: 'present',
  off: 'worked',
  worked: 'off',
};

function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const monthParam = (m: { year: number; month: number }) =>
  `${m.year}-${String(m.month).padStart(2, '0')}`;

/** Mark one day for everyone at the top; see and correct the whole month below. */
export function AttendanceTab() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [day, setDay] = useState(todayISO());
  const [month, setMonth] = useState<string | null>(null); // null: this month
  const [saving, setSaving] = useState<string | null>(null);

  const dayKey = ['staff', 'attendance', day];
  const { data, error, refetch } = useQuery({
    queryKey: dayKey,
    queryFn: () => apiGet<DayRegister>('/api/v1/attendance/', { date: day }),
  });
  const { data: dayInfo } = useQuery({
    queryKey: ['date-conversion', 'ad', day],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/', { ad: day }),
    staleTime: Infinity,
  });
  const registerKey = ['staff', 'register', month];
  const { data: register } = useQuery({
    queryKey: registerKey,
    queryFn: () =>
      apiGet<MonthRegister>('/api/v1/attendance/month/', month ? { month } : undefined),
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

  const markCell = (rowIndex: number, dayIndex: number) => {
    if (!register) return;
    const row = register.rows[rowIndex];
    const status = NEXT[row.cells[dayIndex].status];
    if (!status) return;
    client.setQueryData<MonthRegister>(
      registerKey,
      (old) =>
        old && {
          ...old,
          rows: old.rows.map((r, i) =>
            i === rowIndex
              ? { ...r, cells: r.cells.map((c, j) => (j === dayIndex ? { ...c, status } : c)) }
              : r,
          ),
        },
    );
    void save(row.staff.id, register.days[dayIndex].date, status);
  };

  // Open the register at today's column (late in the month it is off to the right).
  const registerView = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const view = registerView.current;
    const todayHead = view?.querySelector<HTMLElement>('[data-today]');
    const nameHead = view?.querySelector<HTMLElement>('thead th');
    if (view && todayHead && nameHead) {
      view.scrollLeft = Math.max(todayHead.offsetLeft - nameHead.offsetWidth - 4 * 30, 0);
    }
  }, [register?.label]);

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

      {/* -- The month's register --------------------------------------------------- */}
      {register && register.rows.length > 0 && (
        <Card padding={0}>
          <Group justify="space-between" p="var(--ck-card-pad)" pb="sm" gap="sm">
            <div>
              <Text fw={600}>{t('Attendance register')}</Text>
              <Text size="xs" c="dimmed">
                {t('Tap a box to change it. Tap a date to open that day above.')}
              </Text>
            </div>
            <Group gap={6} wrap="nowrap">
              <ActionIcon
                variant="default"
                size={32}
                onClick={() => setMonth(monthParam(register.previous))}
                aria-label={t('Previous month')}
              >
                <IconChevronLeft size={16} />
              </ActionIcon>
              <Text fw={600} miw={110} ta="center">
                {register.label}
              </Text>
              <ActionIcon
                variant="default"
                size={32}
                disabled={!register.next}
                onClick={() => register.next && setMonth(monthParam(register.next))}
                aria-label={t('Next month')}
              >
                <IconChevronRight size={16} />
              </ActionIcon>
            </Group>
          </Group>
          <ScrollArea type="auto" scrollbarSize={8} offsetScrollbars="x" viewportRef={registerView}>
            <table className={classes.register}>
              <thead>
                <tr>
                  <th className={classes.name}>{t('Staff')}</th>
                  {register.days.map((d) => (
                    <th
                      key={d.date}
                      className={clsx(
                        classes.dayHead,
                        d.is_holiday && classes.satHead,
                        d.date === register.today && classes.todayHead,
                        d.date === day && classes.picked,
                      )}
                      data-today={d.date === register.today || undefined}
                      onClick={() => d.date <= register.today && setDay(d.date)}
                      title={formatDate(d.date)}
                    >
                      {d.bs_day}
                      <small>{WEEKDAY_LETTERS[d.weekday]}</small>
                    </th>
                  ))}
                  <th className={classes.total} title={t('Days absent')}>
                    A
                  </th>
                  <th className={classes.total} title={t('Saturdays worked')}>
                    W
                  </th>
                </tr>
              </thead>
              <tbody>
                {register.rows.map((row, i) => (
                  <tr key={row.staff.id}>
                    <td className={classes.name}>
                      <Text size="sm" fw={500} truncate>
                        {row.staff.name}
                      </Text>
                      {row.paid && (
                        <Badge size="xs" color="green" variant="light">
                          {t('Paid')}
                        </Badge>
                      )}
                    </td>
                    {row.cells.map((c, j) => {
                      const d = register.days[j];
                      const future = d.date > register.today;
                      return (
                        <td key={d.date} className={clsx(d.is_holiday && classes.satCol)}>
                          <button
                            type="button"
                            className={clsx(classes.cell, !future && classes[c.status])}
                            disabled={!c.editable || saving === `${row.staff.id}:${d.date}`}
                            onClick={() => markCell(i, j)}
                            aria-label={`${row.staff.name}, ${d.bs_day} ${register.label}: ${t(future ? 'Still to come' : STATUS_NAME[c.status])}`}
                          >
                            {future ? '' : LETTER[c.status]}
                          </button>
                        </td>
                      );
                    })}
                    <td
                      className={classes.total}
                      style={{ color: row.absent ? 'var(--mantine-color-red-7)' : undefined }}
                    >
                      {row.absent || '–'}
                    </td>
                    <td
                      className={classes.total}
                      style={{ color: row.worked ? 'var(--mantine-color-blue-7)' : undefined }}
                    >
                      {row.worked || '–'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <div
            className={classes.legend}
            style={{ padding: 'var(--mantine-spacing-sm) var(--ck-card-pad) var(--ck-card-pad)' }}
          >
            <span>
              <b className={classes.present}>P</b>
              {t('Present')}
            </span>
            <span>
              <b className={classes.absent}>A</b>
              {t('Absent')}
            </span>
            <span>
              <b className={classes.satCol} />
              {t('Saturday off')}
            </span>
            <span>
              <b className={classes.worked}>W</b>
              {t('Worked on Saturday')}
            </span>
            <span>
              <b className={classes.settled}>·</b>
              {t('Before the opening balance')}
            </span>
          </div>
        </Card>
      )}
    </Stack>
  );
}
