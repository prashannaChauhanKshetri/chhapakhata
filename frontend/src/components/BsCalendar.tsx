import { ActionIcon, Center, Loader } from '@mantine/core';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { components } from '@/api/schema';
import { todayISO } from '@/lib/format';

import classes from './BsCalendar.module.css';

type BsMonth = components['schemas']['BsMonth'];

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const monthParam = (m: { year: number; month: number }) =>
  `${m.year}-${String(m.month).padStart(2, '0')}`;

interface BsCalendarProps {
  /** The chosen day (AD, YYYY-MM-DD); its BS month opens first. */
  value: string | null;
  onPick: (ad: string) => void;
  /** Last day that can be chosen (AD). */
  maxDate?: string;
}

/** Pick a day by its Miti. Each day shows its BS number, with the AD day small below. */
export function BsCalendar({ value, onPick, maxDate }: BsCalendarProps) {
  const { t } = useTranslation();
  const [month, setMonth] = useState<string | null>(null); // null: the month of `value`
  const { data } = useQuery({
    queryKey: ['bs-month', month ?? `ad:${value ?? 'today'}`],
    queryFn: () =>
      apiGet<BsMonth>('/api/v1/utils/bs-month/', month ? { month } : { ad: value ?? todayISO() }),
    staleTime: Infinity,
  });
  const today = todayISO();

  if (!data)
    return (
      <Center w={292} h={280}>
        <Loader size="sm" />
      </Center>
    );
  const lead = data.days[0]?.weekday ?? 0;
  return (
    <div>
      <div className={classes.head}>
        <ActionIcon
          variant="default"
          onClick={() => setMonth(monthParam(data.previous))}
          aria-label={t('Previous month')}
        >
          <IconChevronLeft size={16} />
        </ActionIcon>
        <span className={classes.title}>{data.label}</span>
        <ActionIcon
          variant="default"
          onClick={() => setMonth(monthParam(data.next))}
          disabled={!!maxDate && data.days[data.days.length - 1].date >= maxDate}
          aria-label={t('Next month')}
        >
          <IconChevronRight size={16} />
        </ActionIcon>
      </div>
      <div className={classes.grid}>
        {WEEKDAYS.map((w, i) => (
          <div key={w} className={clsx(classes.weekday, i === 6 && classes.saturday)}>
            {t(w)}
          </div>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <span key={`lead-${i}`} />
        ))}
        {data.days.map((d) => {
          const ad = new Date(`${d.date}T00:00:00`);
          return (
            <button
              key={d.date}
              type="button"
              className={clsx(
                classes.day,
                d.weekday === 6 && classes.saturday,
                d.date === today && classes.today,
                d.date === value && classes.selected,
              )}
              disabled={!!maxDate && d.date > maxDate}
              onClick={() => onPick(d.date)}
              aria-label={`${d.bs_day} ${data.label}`}
              aria-pressed={d.date === value}
            >
              <span className={classes.bs}>{d.bs_day}</span>
              <span className={classes.ad}>
                {ad.getDate() === 1 || d.bs_day === 1
                  ? ad.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
                  : ad.getDate()}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
