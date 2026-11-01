import {
  Alert,
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Textarea,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconInfoCircle } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import type { Customer, OpeningBalance } from '@/api/types';
import { Balance } from '@/components/Balance';
import { DualDate } from '@/components/DualDate';
import { FormSkeleton } from '@/components/Skeletons';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatDateTime, formatNPR, toNumber, todayISO } from '@/lib/format';

type Side = 'due' | 'advance';

function History({ data }: { data: OpeningBalance }) {
  const { t } = useTranslation();
  if (data.entries.length < 2) return null;
  return (
    <Stack gap={4}>
      <Text size="sm" fw={500}>
        {t('Changes')}
      </Text>
      <Table fz="sm" verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('When')}</Table.Th>
            <Table.Th>{t('Change')}</Table.Th>
            <Table.Th>{t('By')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.entries.map((e, i) => (
            <Table.Tr key={i}>
              <Table.Td>{formatDateTime(e.created_at)}</Table.Td>
              <Table.Td>
                <Balance value={toNumber(e.debit) - toNumber(e.credit)} />
                <Text size="xs" c="dimmed">
                  {e.narration}
                </Text>
              </Table.Td>
              <Table.Td>{e.created_by}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

function OpeningBalanceForm({
  customer,
  data,
  onDone,
}: {
  customer: Customer;
  data: OpeningBalance;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const current = toNumber(data.amount);
  const isSet = data.entries.length > 0;
  const form = useForm({
    initialValues: {
      amount: (isSet ? Math.abs(current) : '') as number | string,
      side: (current < 0 ? 'advance' : 'due') as Side,
      as_of: data.default_date as string | null,
      reason: '',
    },
    validate: {
      amount: (v) => (v === '' || toNumber(v) < 0 ? t('Enter the amount (0 or more)') : null),
      reason: (v) =>
        isSet && v.trim().length < 5 ? t('Write why it is changing (at least 5 characters)') : null,
    },
  });
  const target = toNumber(form.values.amount) * (form.values.side === 'advance' ? -1 : 1);

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/customers/{id}/opening-balance/', {
          params: { path: { id: customer.id } },
          body: {
            amount: String(target),
            as_of: isSet ? null : values.as_of,
            reason: values.reason,
          },
        }),
      );
      await Promise.all([
        client.invalidateQueries({ queryKey: ['customer', customer.id] }),
        client.invalidateQueries({ queryKey: ['customers'] }),
        client.invalidateQueries({ queryKey: ['ledger'] }),
      ]);
      notifySuccess(isSet ? t('Opening balance corrected') : t('Opening balance saved'));
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });

  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {t(
            'What the customer owed the shop (or had paid in advance) when last fiscal year closed. It becomes the opening balance of every statement from then on.',
          )}
        </Text>

        {isSet ? (
          <Group gap="xs">
            <Text size="sm">{t('Now')}:</Text>
            <Balance value={data.amount} />
            <Text size="sm" c="dimmed">
              · {t('as on')}
            </Text>
            <DualDate ad={data.date} bs={data.date_bs} inline />
          </Group>
        ) : (
          data.has_other_entries && (
            <Alert color="amber" variant="light" icon={<IconInfoCircle size={18} />}>
              {t(
                'This customer already has bills, payments or imported work in the system. Enter only what was owed from before those, or it will be counted twice.',
              )}
            </Alert>
          )
        )}

        <SegmentedControl
          fullWidth
          data={[
            { value: 'due', label: t('Customer owes us (Dr)') },
            { value: 'advance', label: t('Advance with us (Cr)') },
          ]}
          {...form.getInputProps('side')}
        />
        <NumberInput
          label={t('Amount')}
          prefix="Rs. "
          thousandSeparator=","
          decimalScale={2}
          min={0}
          allowNegative={false}
          data-autofocus
          {...form.getInputProps('amount')}
        />
        {!isSet && (
          <DatePickerInput
            label={t('As on')}
            description={t('Usually the last day of the previous fiscal year ({{date}} BS)', {
              date: data.default_date_bs,
            })}
            valueFormat="D MMM YYYY"
            maxDate={todayISO()}
            {...form.getInputProps('as_of')}
          />
        )}
        <Textarea
          label={isSet ? t('Reason for the change') : t('Note (optional)')}
          placeholder={isSet ? t('e.g. the old khata showed a different figure') : undefined}
          autosize
          minRows={2}
          {...form.getInputProps('reason')}
        />
        {isSet && target !== current && (
          <Text size="sm">
            {t(
              'A correction of {{diff}} is posted on the same date; the earlier figure stays in the history.',
              {
                diff: formatNPR(target - current),
              },
            )}
          </Text>
        )}

        <History data={data} />

        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={isSet && target === current}>
            {isSet ? t('Save correction') : t('Save opening balance')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function OpeningBalanceLoader({ customer, onDone }: { customer: Customer; onDone: () => void }) {
  const { data } = useQuery({
    queryKey: ['customer', customer.id, 'opening-balance'],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/customers/{id}/opening-balance/', {
          params: { path: { id: customer.id } },
        }),
      ),
  });
  if (!data) return <FormSkeleton sections={1} />;
  return <OpeningBalanceForm customer={customer} data={data} onDone={onDone} />;
}

/** Set or correct the balance a customer carried in from the previous year (owner). */
export function openOpeningBalance(customer: Customer, title: string) {
  const modalId = modals.open({
    title,
    size: 'lg',
    children: <OpeningBalanceLoader customer={customer} onDone={() => modals.close(modalId)} />,
  });
}
