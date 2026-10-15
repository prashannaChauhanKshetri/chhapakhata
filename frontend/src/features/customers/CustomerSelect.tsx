import { ActionIcon, Group, Select, Text, Tooltip } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconUserPlus } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/http';
import type { Customer, Paginated } from '@/api/types';
import { formatNPR, toNumber } from '@/lib/format';

import { openCustomerModal } from './CustomerForm';

interface CustomerSelectProps {
  value: Customer | null;
  onChange: (customer: Customer | null) => void;
  error?: React.ReactNode;
  disabled?: boolean;
  label?: string;
}

/** Search customers by name, phone or PAN; add a new one without leaving the form. */
export function CustomerSelect({ value, onChange, error, disabled, label }: CustomerSelectProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 250);
  const { data, isFetching } = useQuery({
    queryKey: ['customers', 'picker', debounced],
    queryFn: () =>
      apiGet<Paginated<Customer>>('/api/v1/customers/', {
        search: debounced,
        is_active: 'true',
        page_size: 20,
      }),
    enabled: !disabled,
    placeholderData: (previous) => previous,
  });

  const options = useMemo(() => {
    const list = data?.results ?? [];
    const all = value && !list.some((c) => c.id === value.id) ? [value, ...list] : list;
    return all;
  }, [data, value]);

  const label_ = (c: Customer) => (c.phone ? `${c.name} · ${c.phone}` : c.name);

  return (
    <Group gap="xs" align="flex-start" wrap="nowrap">
      <Select
        style={{ flex: 1 }}
        label={label ?? t('Customer')}
        placeholder={t('Search by name, phone or PAN')}
        searchable
        clearable
        disabled={disabled}
        error={error}
        value={value ? String(value.id) : null}
        searchValue={search}
        onSearchChange={setSearch}
        data={options.map((c) => ({ value: String(c.id), label: label_(c) }))}
        filter={({ options: opts }) => opts}
        nothingFoundMessage={
          isFetching ? t('Searching…') : t('No match. Use the + button to add a new customer.')
        }
        onChange={(id) => onChange(options.find((c) => String(c.id) === id) ?? null)}
        renderOption={({ option }) => {
          const c = options.find((x) => String(x.id) === option.value);
          if (!c) return option.label;
          const balance = toNumber(c.balance);
          return (
            <Group justify="space-between" w="100%" wrap="nowrap" gap="sm">
              <div style={{ minWidth: 0 }}>
                <Text size="sm" lineClamp={1}>
                  {c.name}
                </Text>
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {[c.phone, c.address].filter(Boolean).join(' · ') || '—'}
                </Text>
              </div>
              {balance !== 0 && (
                <Text size="xs" c={balance > 0 ? 'red.7' : 'green.7'} className="num">
                  {balance > 0 ? t('Due') : t('Advance')} {formatNPR(Math.abs(balance))}
                </Text>
              )}
            </Group>
          );
        }}
      />
      {!disabled && (
        <Tooltip label={t('New customer')}>
          <ActionIcon
            variant="default"
            size={36}
            mt={label === '' ? 0 : 25}
            aria-label={t('New customer')}
            onClick={() => openCustomerModal({ initialName: search, onSaved: (c) => onChange(c) })}
          >
            <IconUserPlus size={18} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );
}
