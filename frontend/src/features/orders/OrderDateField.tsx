import { SimpleGrid, TextInput } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { DateConversion } from '@/api/types';
import { todayISO } from '@/lib/format';

const BS_PATTERN = /^(\d{4})[.\-/ ](\d{1,2})[.\-/ ](\d{1,2})$/;

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
  value: string;
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
  const { data } = useQuery({
    queryKey: ['date-conversion', 'ad', value],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/', { ad: value }),
    enabled: !!value,
    staleTime: Infinity,
  });
  const bsText = bsDraft ?? (data && data.ad === value ? data.bs.replaceAll('-', '.') : '');

  const readBs = async () => {
    if (bsDraft === null) return; // nothing typed
    const match = BS_PATTERN.exec(bsText.trim());
    if (!match) {
      setBsError(t('Write the Miti like 2083.08.04'));
      return;
    }
    const bs = `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`;
    try {
      const converted = await apiGet<DateConversion>('/api/v1/utils/date/', { bs });
      if (converted.ad > todayISO()) {
        setBsError(t('An order cannot be dated in the future.'));
        return;
      }
      setBsError(null);
      setBsDraft(null);
      onChange(converted.ad);
    } catch {
      setBsError(t('There is no such Miti.'));
    }
  };

  const late = !!value && value < todayISO();
  return (
    <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
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
      />
      <DatePickerInput
        label={label ? `${label} (AD)` : t('Date (AD)')}
        valueFormat="D MMM YYYY"
        maxDate={todayISO()}
        value={value}
        onChange={(v) => {
          if (v) {
            setBsError(null);
            setBsDraft(null);
            onChange(String(v).slice(0, 10));
          }
        }}
      />
    </SimpleGrid>
  );
}
