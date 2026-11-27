import { ActionIcon, Popover, SimpleGrid, TextInput } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconCalendar } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { DateConversion } from '@/api/types';
import { BsCalendar } from '@/components/BsCalendar';
import { todayISO } from '@/lib/format';

const BS_PATTERN = /^(\d{4})[.\-/ ](\d{1,2})[.\-/ ](\d{1,2})$/;

/** Typed Miti still being converted on the server (left before the answer came). */
const converting = new Set<Promise<void>>();
/** Boxes whose typed Miti could not be read (they show the reason). */
const unreadable = new Set<symbol>();

/**
 * Wait until every typed Miti has been converted and passed on, then say whether
 * all of them could be read. Call it before reading the dates to save or print:
 * clicking Save right after typing a Miti would otherwise use the date from
 * before, and a Miti that cannot be read would be quietly ignored.
 */
export async function datesSettled(): Promise<boolean> {
  while (converting.size > 0) await Promise.all([...converting]);
  return unreadable.size === 0;
}

/** A form's submit handler that first waits for the dates ({@link datesSettled}). */
export function afterDates(submit: () => void) {
  return (event?: React.FormEvent) => {
    event?.preventDefault();
    void datesSettled().then((ok) => ok && submit());
  };
}

/**
 * The order date as Miti (BS, typed) and AD (calendar), kept in step.
 * Today by default; any past date for orders entered late; never the future.
 */
export function OrderDateField({
  value,
  onChange,
  error,
  label,
  showHint = true,
}: {
  /** AD date (YYYY-MM-DD); empty when not chosen yet. */
  value: string | null;
  onChange: (ad: string) => void;
  error?: React.ReactNode;
  /** e.g. "From"; the boxes read "From (Miti)" and "From (AD)". */
  label?: string;
  showHint?: boolean;
}) {
  const { t } = useTranslation();
  // What is being typed; null shows the Miti of the chosen date.
  const [bsDraft, setBsDraft] = useState<string | null>(null);
  const [bsError, setBsError] = useState<string | null>(null);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ['date-conversion', 'ad', value],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/', { ad: value }),
    enabled: !!value,
    staleTime: Infinity,
  });
  const bsText = bsDraft ?? (data && data.ad === value ? data.bs.replaceAll('-', '.') : '');

  const [id] = useState(() => Symbol('miti'));
  useEffect(() => () => void unreadable.delete(id), [id]);
  const fail = (message: string) => {
    setBsError(message);
    unreadable.add(id);
  };

  /** A date was chosen: show its Miti, with no error. */
  const settle = () => {
    setBsError(null);
    setBsDraft(null);
    unreadable.delete(id);
  };

  const readBs = () => {
    if (bsDraft === null) return; // nothing typed
    const job = convert();
    converting.add(job);
    void job.finally(() => converting.delete(job));
  };

  const convert = async () => {
    const match = BS_PATTERN.exec(bsText.trim());
    if (!match) {
      fail(t('Write the Miti like 2083.08.04'));
      return;
    }
    const bs = `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
    try {
      const converted = await apiGet<DateConversion>('/api/v1/utils/date/', { bs });
      if (converted.ad > todayISO()) {
        fail(t('The date cannot be in the future.'));
        return;
      }
      settle();
      onChange(converted.ad);
    } catch {
      fail(t('There is no such Miti.'));
    }
  };

  const late = !!value && value < todayISO();
  return (
    <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
      <Popover
        opened={calendarOpen}
        onChange={setCalendarOpen}
        position="bottom-start"
        shadow="md"
        trapFocus={false}
        returnFocus={false}
      >
        <Popover.Target>
          <TextInput
            label={label ? `${label} (Miti)` : t('Order date (Miti)')}
            placeholder="2083.08.04"
            value={bsText}
            onChange={(e) => setBsDraft(e.currentTarget.value)}
            onBlur={() => void readBs()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void readBs();
              }
            }}
            description={
              !showHint
                ? undefined
                : late
                  ? t('Entered late: not today')
                  : t('Today, or an earlier day')
            }
            inputWrapperOrder={['label', 'input', 'description', 'error']}
            error={bsError ?? error}
            onClick={() => setCalendarOpen(true)}
            rightSection={
              <ActionIcon
                onClick={(e) => {
                  e.stopPropagation();
                  setCalendarOpen((o) => !o);
                }}
                aria-label={t('Nepali calendar')}
              >
                <IconCalendar size={16} />
              </ActionIcon>
            }
          />
        </Popover.Target>
        <Popover.Dropdown p="xs">
          <BsCalendar
            value={value || null}
            maxDate={todayISO()}
            onPick={(ad) => {
              settle();
              setCalendarOpen(false);
              onChange(ad);
            }}
          />
        </Popover.Dropdown>
      </Popover>
      <DatePickerInput
        label={label ? `${label} (AD)` : t('Date (AD)')}
        valueFormat="D MMM YYYY"
        maxDate={todayISO()}
        value={value || null}
        onChange={(v) => {
          if (v) {
            settle();
            onChange(String(v).slice(0, 10));
          }
        }}
      />
    </SimpleGrid>
  );
}
