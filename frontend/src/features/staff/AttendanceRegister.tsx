import { ActionIcon, Anchor, Badge, Card, Group, ScrollArea, Text } from '@mantine/core';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { components } from '@/api/schema';
import type { DayStatus } from '@/api/types';
import { notifyError } from '@/lib/forms';
import { formatDate } from '@/lib/format';

import classes from './AttendanceRegister.module.css';

type MonthRegister = components['schemas']['MonthRegister'];

const WEEKDAY_LETTERS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
/** What a box shows. */
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

const monthParam = (m: { year: number; month: number }) =>
  `${m.year}-${String(m.month).padStart(2, '0')}`;

interface AttendanceRegisterProps {
  /** The day open above it (highlighted). */
  pickedDay?: string;
  /** Tapping a date opens that day; without it dates are not tappable. */
  onPickDay?: (date: string) => void;
  /** Show a link to the Attendance tab (on the dashboard). */
  withLink?: boolean;
}

/**
 * The month's attendance for everyone, like the paper register: one row per
 * worker, one box per day. A tap on a box switches present/absent (or, on
 * Saturday, off/worked).
 */
export function AttendanceRegister({ pickedDay, onPickDay, withLink }: AttendanceRegisterProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [month, setMonth] = useState<string | null>(null); // null: this month
  const [saving, setSaving] = useState<string | null>(null);
  const key = ['staff', 'register', month];
  const { data: register } = useQuery({
    queryKey: key,
    queryFn: () =>
      apiGet<MonthRegister>('/api/v1/attendance/month/', month ? { month } : undefined),
  });

  // Open at today's column: late in the month it is off to the right on a phone.
  const view = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const viewport = view.current;
    const todayHead = viewport?.querySelector<HTMLElement>('[data-today]');
    const nameHead = viewport?.querySelector<HTMLElement>('thead th');
    if (viewport && todayHead && nameHead) {
      viewport.scrollLeft = Math.max(todayHead.offsetLeft - nameHead.offsetWidth - 4 * 30, 0);
    }
  }, [register?.label]);

  const toggle = async (rowIndex: number, dayIndex: number) => {
    if (!register) return;
    const row = register.rows[rowIndex];
    const status = NEXT[row.cells[dayIndex].status];
    if (!status) return;
    const date = register.days[dayIndex].date;
    client.setQueryData<MonthRegister>(
      key,
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
    setSaving(`${row.staff.id}:${date}`);
    try {
      await unwrap(
        api.POST('/api/v1/attendance/', { body: { staff: row.staff.id, date, status } }),
      );
    } catch (e) {
      notifyError(e, t('Could not mark attendance'));
    } finally {
      setSaving(null);
      // The day list, the totals, the calendar and the month's pay all change.
      await client.invalidateQueries({ queryKey: ['staff'] });
    }
  };

  if (!register || register.rows.length === 0) return null;
  return (
    <Card padding={0}>
      <Group justify="space-between" p="var(--ck-card-pad)" pb="sm" gap="sm">
        <div>
          <Group gap="sm" align="baseline">
            <Text fw={600}>{t('Attendance register')}</Text>
            {withLink && (
              <Anchor component={Link} to="/staff/attendance" size="sm">
                {t('Open attendance')}
              </Anchor>
            )}
          </Group>
          <Text size="xs" c="dimmed">
            {onPickDay
              ? t('Tap a box to change it. Tap a date to open that day above.')
              : t('Tap a box to change it.')}
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
      <ScrollArea type="auto" scrollbarSize={8} offsetScrollbars="x" viewportRef={view}>
        <table className={classes.register}>
          <thead>
            <tr>
              <th className={classes.name}>{t('Staff')}</th>
              {register.days.map((d) => {
                const pickable = !!onPickDay && d.date <= register.today;
                return (
                  <th
                    key={d.date}
                    className={clsx(
                      classes.dayHead,
                      d.is_holiday && classes.satHead,
                      d.date === register.today && classes.todayHead,
                      d.date === pickedDay && classes.picked,
                    )}
                    data-today={d.date === register.today || undefined}
                    data-pickable={pickable || undefined}
                    onClick={() => pickable && onPickDay(d.date)}
                    title={formatDate(d.date)}
                  >
                    {d.bs_day}
                    <small>{WEEKDAY_LETTERS[d.weekday]}</small>
                  </th>
                );
              })}
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
                        onClick={() => void toggle(i, j)}
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
  );
}
