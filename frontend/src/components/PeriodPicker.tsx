import { Group, Select } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { Period } from '@/api/types';

export interface PeriodValue {
  /** A named period key, `all`, or `custom`. */
  key: string;
  from: string | null;
  to: string | null;
}

export function usePeriods() {
  return useQuery({
    queryKey: ['utils', 'periods'],
    queryFn: () => apiGet<Period[]>('/api/v1/utils/periods/'),
    staleTime: 60 * 60_000,
  });
}

/** Resolve a named period (e.g. `this_fy`) to dates once the list has loaded. */
export function resolvePeriod(value: PeriodValue, periods: Period[] | undefined): PeriodValue {
  if (value.key === 'custom' || value.key === 'all') return value;
  const match = periods?.find((p) => p.key === value.key);
  return match ? { key: value.key, from: match.date_from, to: match.date_to } : value;
}

interface PeriodPickerProps {
  value: PeriodValue;
  onChange: (value: PeriodValue) => void;
  allowAll?: boolean;
}

/** Period presets in the shop's calendar (BS months, fiscal years) plus a custom range. */
export function PeriodPicker({ value, onChange, allowAll = true }: PeriodPickerProps) {
  const { t } = useTranslation();
  const { data: periods = [] } = usePeriods();
  const options = [
    ...periods.map((p) => ({ value: p.key, label: p.label })),
    ...(allowAll ? [{ value: 'all', label: t('All time') }] : []),
    { value: 'custom', label: t('Custom dates…') },
  ];
  return (
    <Group gap="xs" wrap="wrap" align="flex-end">
      <Select
        label={t('Period')}
        data={options}
        value={value.key}
        allowDeselect={false}
        w={250}
        onChange={(key) => {
          if (!key) return;
          if (key === 'all') onChange({ key, from: null, to: null });
          else if (key === 'custom') onChange({ ...value, key });
          else onChange(resolvePeriod({ key, from: null, to: null }, periods));
        }}
      />
      {value.key === 'custom' && (
        <DatePickerInput
          type="range"
          label={t('From – to')}
          value={[value.from, value.to]}
          onChange={([from, to]) => onChange({ key: 'custom', from, to })}
          valueFormat="D MMM YYYY"
          maxDate={dayjs().format('YYYY-MM-DD')}
          w={260}
        />
      )}
    </Group>
  );
}
