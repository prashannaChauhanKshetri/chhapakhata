import {
  ActionIcon,
  Badge,
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
import type { DayRegister, DayRow, DayStatus } from '@/api/types';
import { QueryError } from '@/components/QueryError';
import { notifyError } from '@/lib/forms';
import { todayISO } from '@/lib/format';

import { OrderDateField } from '../orders/OrderDateField';
import { openAttendanceCalendar } from './AttendanceCalendar';

function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** The daily register: everyone is present unless marked absent; Saturday is off unless worked. */
export function AttendanceTab() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [day, setDay] = useState(todayISO());
  const [saving, setSaving] = useState<number | null>(null);
  const key = ['staff', 'attendance', day];
  const { data, error, refetch } = useQuery({
    queryKey: key,
    queryFn: () => apiGet<DayRegister>('/api/v1/attendance/', { date: day }),
  });

  const mark = async (row: DayRow, status: DayStatus) => {
    setSaving(row.staff.id);
    // Show the change at once; put it back if the server refuses.
    client.setQueryData<DayRegister>(
      key,
      (old) =>
        old && {
          ...old,
          rows: old.rows.map((r) => (r.staff.id === row.staff.id ? { ...r, status } : r)),
        },
    );
    try {
      await unwrap(
        api.POST('/api/v1/attendance/', { body: { staff: row.staff.id, date: day, status } }),
      );
      await client.invalidateQueries({ queryKey: ['staff', 'salary'] });
    } catch (e) {
      notifyError(e, t('Could not mark attendance'));
      await refetch();
    } finally {
      setSaving(null);
    }
  };

  const holiday = data?.is_holiday ?? false;
  const absent = data?.rows.filter((r) => r.status === 'absent').length ?? 0;
  const worked = data?.rows.filter((r) => r.status === 'worked').length ?? 0;
  const isToday = day >= todayISO();

  return (
    <Stack gap="md">
      <Card>
        <Group align="flex-end" gap="xs" wrap="nowrap">
          <Tooltip label={t('Previous day')}>
            <ActionIcon
              variant="default"
              size={36}
              mb={2}
              onClick={() => setDay(shiftDay(day, -1))}
              aria-label={t('Previous day')}
            >
              <IconChevronLeft size={18} />
            </ActionIcon>
          </Tooltip>
          <div style={{ flex: 1, minWidth: 0 }}>
            <OrderDateField value={day} onChange={setDay} label={t('Day')} showHint={false} />
          </div>
          <Tooltip label={t('Next day')}>
            <ActionIcon
              variant="default"
              size={36}
              mb={2}
              disabled={isToday}
              onClick={() => setDay(shiftDay(day, 1))}
              aria-label={t('Next day')}
            >
              <IconChevronRight size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
        {data && (
          <Group gap="xs" mt="sm">
            {holiday ? (
              <Badge color="blue">{t('Saturday: weekly holiday')}</Badge>
            ) : (
              <Badge color={absent ? 'red' : 'green'}>
                {absent ? t('{{n}} absent', { n: absent }) : t('Everyone present')}
              </Badge>
            )}
            {holiday && worked > 0 && (
              <Badge color="blue" variant="outline">
                {t('{{n}} worked (one day extra each)', { n: worked })}
              </Badge>
            )}
          </Group>
        )}
      </Card>

      {error ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : data && data.rows.length === 0 ? (
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
          <div className="ck-rows" style={{ borderTop: 0 }}>
            {data?.rows.map((row) => (
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
                    <Text fw={500} lineClamp={1}>
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
                    size="sm"
                    disabled={row.locked || saving === row.staff.id}
                    value={row.status}
                    color={
                      row.status === 'absent' ? 'red' : row.status === 'worked' ? 'blue' : 'green'
                    }
                    onChange={(v) => void mark(row, v as DayStatus)}
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
    </Stack>
  );
}
