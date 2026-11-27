import {
  Alert,
  Button,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { components } from '@/api/schema';
import type { MonthSheet, Staff } from '@/api/types';
import { Money } from '@/components/Money';
import { handleFormError, notifyError, notifySuccess } from '@/lib/forms';
import { formatNPR, todayISO, toNumber } from '@/lib/format';
import { PAYMENT_MODES } from '@/lib/status';

import { afterDates, OrderDateField } from '../orders/OrderDateField';

// -- Add or edit a worker -------------------------------------------------------------

type MonthRange = components['schemas']['MonthRange'];
const monthKey = (m: { year: number; month: number }) =>
  `${m.year}-${String(m.month).padStart(2, '0')}`;

/** Who owes whom up to the balance month. */
type Direction = 'to_worker' | 'to_shop';

function StaffForm({ staff, onDone }: { staff?: Staff; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data: months } = useQuery({
    queryKey: ['staff', 'months'],
    queryFn: () => apiGet<MonthRange[]>('/api/v1/salary/months/'),
    staleTime: 10 * 60_000,
  });
  const opening = staff ? toNumber(staff.opening_balance) : 0;
  const form = useForm({
    initialValues: {
      name: staff?.name ?? '',
      job_title: staff?.job_title ?? '',
      phone: staff?.phone ?? '',
      monthly_salary: (staff ? toNumber(staff.monthly_salary) : '') as number | string,
      saturday_pay: (staff?.saturday_pay != null ? toNumber(staff.saturday_pay) : '') as
        | number
        | string,
      joined_on: staff?.joined_on ?? todayISO(),
      is_active: staff?.is_active ?? true,
      left_on: (staff?.left_on ?? null) as string | null,
      notes: staff?.notes ?? '',
      // New staff: someone already working here starts from a balance (to last month).
      already: false,
      // null: not chosen yet, so the form offers last month.
      balance: (staff?.balance_year
        ? monthKey({ year: staff.balance_year, month: staff.balance_month! })
        : staff
          ? ''
          : null) as string | null,
      balance_amount: (opening ? Math.abs(opening) : '') as number | string,
      direction: (opening < 0 ? 'to_shop' : 'to_worker') as Direction,
    },
    validate: {
      name: (v) => (v.trim() ? null : t('Enter the name')),
      monthly_salary: (v) => (v === '' || toNumber(v) < 0 ? t('Enter the monthly salary') : null),
      left_on: (v, values) => (!values.is_active && !v ? t('Enter the last working day') : null),
    },
  });

  const lastMonth = months?.[1] ? monthKey(months[1]) : '';
  const withBalance = !!staff || form.values.already;
  const balance = form.values.balance ?? (withBalance ? lastMonth : '');
  const chosen = months?.find((m) => monthKey(m) === balance);
  const after = chosen ? months?.[months.indexOf(chosen) - 1] : undefined;

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const [year, month] = balance ? balance.split('-').map(Number) : [null, null];
    const amount = toNumber(values.balance_amount);
    const body = {
      name: values.name,
      job_title: values.job_title,
      phone: values.phone,
      notes: values.notes,
      is_active: values.is_active,
      monthly_salary: String(values.monthly_salary),
      // Empty: one day's pay for each Saturday worked.
      saturday_pay: values.saturday_pay === '' ? null : String(values.saturday_pay),
      left_on: values.is_active ? values.left_on || null : values.left_on,
      balance_year: year,
      balance_month: month,
      opening_balance: String(balance ? (values.direction === 'to_shop' ? -amount : amount) : 0),
      // Already working here: pay counts from the day after the balance month.
      joined_on:
        !staff && values.already && chosen ? (after?.start ?? todayISO()) : values.joined_on,
    };
    try {
      await unwrap(
        staff
          ? api.PATCH('/api/v1/staff/{id}/', { params: { path: { id: staff.id } }, body })
          : api.POST('/api/v1/staff/', { body }),
      );
      await client.invalidateQueries({ queryKey: ['staff'] });
      notifySuccess(staff ? t('{{name}} updated', { name: values.name }) : t('Staff added'));
      onDone();
    } catch (e) {
      handleFormError(e, form);
    } finally {
      setBusy(false);
    }
  });

  const monthOptions = (months ?? []).map((m) => ({ value: monthKey(m), label: m.label }));

  // Only for a worker with no salary paid and no advance given (e.g. added by mistake).
  const confirmDelete = () =>
    staff &&
    modals.openConfirmModal({
      title: t('Delete {{name}}?', { name: staff.name }),
      children: (
        <Text size="sm">
          {t(
            'The worker and their attendance marks are removed. Use this only for a worker added by mistake; for someone who left, switch off “Still working here” instead.',
          )}
        </Text>
      ),
      labels: { confirm: t('Delete worker'), cancel: t('Keep') },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await unwrap(api.DELETE('/api/v1/staff/{id}/', { params: { path: { id: staff.id } } }));
          await client.invalidateQueries({ queryKey: ['staff'] });
          notifySuccess(t('{{name}} deleted', { name: staff.name }));
          onDone();
        } catch (e) {
          notifyError(e, t('Could not delete'));
        }
      },
    });

  return (
    <form onSubmit={afterDates(submit)} noValidate>
      <Stack gap="sm">
        {!staff && (
          <SegmentedControl
            fullWidth
            data={[
              { value: 'new', label: t('New worker') },
              { value: 'already', label: t('Already working here') },
            ]}
            value={form.values.already ? 'already' : 'new'}
            onChange={(v) => form.setFieldValue('already', v === 'already')}
          />
        )}
        <TextInput label={t('Name')} required data-autofocus {...form.getInputProps('name')} />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <TextInput
            label={t('Work')}
            placeholder={t('e.g. Designer, Fitter')}
            {...form.getInputProps('job_title')}
          />
          <TextInput label={t('Phone')} {...form.getInputProps('phone')} />
        </SimpleGrid>
        <NumberInput
          label={t('Monthly salary (Rs)')}
          required
          min={0}
          thousandSeparator=","
          decimalScale={2}
          {...form.getInputProps('monthly_salary')}
        />
        {(staff || !form.values.already) && (
          // Miti first, with the Nepali calendar: AD dates picked in the wrong year
          // gave joining dates still to come.
          <OrderDateField
            label={t('Joined on')}
            value={form.values.joined_on}
            onChange={(ad) => form.setFieldValue('joined_on', ad)}
            error={form.errors.joined_on}
            showHint={false}
          />
        )}
        <NumberInput
          label={t('Saturday pay (Rs)')}
          description={t(
            'Extra for each Saturday worked. Leave empty for one day’s pay (double for that day).',
          )}
          placeholder={t('One day’s pay')}
          min={0}
          thousandSeparator=","
          decimalScale={2}
          inputWrapperOrder={['label', 'input', 'description', 'error']}
          {...form.getInputProps('saturday_pay')}
        />

        {withBalance && (
          <Paper withBorder radius="md" p="sm" bg="slate.0">
            <Stack gap="xs">
              <Text size="sm" fw={600}>
                {t('Balance up to now')}
              </Text>
              <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
                <Select
                  label={t('Up to the end of')}
                  data={[
                    ...(staff ? [{ value: '', label: t('No balance') }] : []),
                    ...monthOptions,
                  ]}
                  value={balance}
                  onChange={(v) => form.setFieldValue('balance', v ?? '')}
                  error={form.errors.balance_month}
                />
                <NumberInput
                  label={t('Amount (Rs)')}
                  placeholder="0"
                  min={0}
                  thousandSeparator=","
                  decimalScale={2}
                  disabled={!balance}
                  {...form.getInputProps('balance_amount')}
                  error={form.errors.opening_balance}
                />
              </SimpleGrid>
              {balance && (
                <SegmentedControl
                  fullWidth
                  data={[
                    { value: 'to_worker', label: t('Shop owes the worker') },
                    { value: 'to_shop', label: t('Worker owes the shop') },
                  ]}
                  {...form.getInputProps('direction')}
                />
              )}
              <Text size="xs" c="dimmed">
                {balance && chosen
                  ? t(
                      'Unpaid salary, or an old advance, up to the end of {{month}}. Pay is counted from {{next}}; this balance is settled in that month’s salary.',
                      { month: chosen.label, next: after?.label ?? t('next month') },
                    )
                  : t('No balance: pay is counted from the joining date.')}
              </Text>
            </Stack>
          </Paper>
        )}

        {staff && (
          <Switch
            label={t('Still working here')}
            description={t('Left the shop? Switch this off and enter the last working day.')}
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
        )}
        {staff && !form.values.is_active && (
          <OrderDateField
            label={t('Last working day')}
            value={form.values.left_on}
            onChange={(ad) => form.setFieldValue('left_on', ad)}
            error={form.errors.left_on}
            showHint={false}
          />
        )}
        <Textarea label={t('Notes')} {...form.getInputProps('notes')} />
        {staff && (
          <Text size="xs" c="dimmed">
            {t('A new salary counts from months not yet paid. Paid months keep what was paid.')}
          </Text>
        )}
        <Group justify="space-between" gap="xs">
          {staff?.can_delete ? (
            <Button variant="subtle" color="red" onClick={confirmDelete}>
              {t('Delete worker')}
            </Button>
          ) : (
            <span />
          )}
          <Group gap="xs">
            <Button variant="default" onClick={onDone}>
              {t('Cancel')}
            </Button>
            {/* The balance month comes from the month list: wait for it, or a worker
                already here could be saved without their balance. */}
            <Button type="submit" loading={busy} disabled={withBalance && !months}>
              {staff ? t('Save') : t('Add staff')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </form>
  );
}

export function openStaffForm(staff?: Staff) {
  const id = modals.open({
    title: staff ? staff.name : 'Add staff',
    children: <StaffForm staff={staff} onDone={() => modals.close(id)} />,
  });
}

// -- Give an advance ------------------------------------------------------------------

function AdvanceForm({
  staff,
  onDone,
}: {
  staff: { id: number; name: string };
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: { date: todayISO(), amount: '' as number | string, note: '' },
    validate: { amount: (v) => (toNumber(v) > 0 ? null : t('Enter the amount')) },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/staff-advances/', {
          body: {
            staff: staff.id,
            date: values.date,
            amount: String(values.amount),
            note: values.note,
          },
        }),
      );
      await client.invalidateQueries({ queryKey: ['staff'] });
      notifySuccess(
        t('Advance {{amount}} to {{name}}', { amount: formatNPR(values.amount), name: staff.name }),
      );
      onDone();
    } catch (e) {
      handleFormError(e, form);
    } finally {
      setBusy(false);
    }
  });

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {t('Taken off the salary of the month it is given in.')}
        </Text>
        <NumberInput
          label={t('Amount (Rs)')}
          required
          min={0}
          thousandSeparator=","
          decimalScale={2}
          data-autofocus
          {...form.getInputProps('amount')}
        />
        <OrderDateField
          label={t('Given on')}
          value={form.values.date}
          onChange={(ad) => form.setFieldValue('date', ad)}
          error={form.errors.date}
          showHint={false}
        />
        <TextInput label={t('Note')} placeholder={t('Optional')} {...form.getInputProps('note')} />
        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('Give advance')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openAdvanceForm(staff: { id: number; name: string }) {
  const id = modals.open({
    title: `Advance · ${staff.name}`,
    children: <AdvanceForm staff={staff} onDone={() => modals.close(id)} />,
  });
}

// -- Pay the month --------------------------------------------------------------------

function PaySalaryForm({
  sheet,
  year,
  month,
  label,
  onDone,
}: {
  sheet: MonthSheet;
  year: number;
  month: number;
  label: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      paid_on: todayISO(),
      mode: 'cash' as components['schemas']['ModeEnum'],
      note: '',
    },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const payment = await unwrap(
        api.POST('/api/v1/salary/pay/', {
          body: { staff: sheet.staff.id, year, month, ...values },
        }),
      );
      await client.invalidateQueries({ queryKey: ['staff'] });
      notifySuccess(
        t('{{amount}} paid to {{name}} for {{month}}', {
          amount: formatNPR(payment.net_paid),
          name: sheet.staff.name,
          month: label,
        }),
      );
      onDone();
      void openFile(`/api/v1/salary-payments/${payment.id}/slip/`).catch((e) =>
        notifyError(e, t('Could not open the salary slip')),
      );
    } catch (e) {
      handleFormError(e, form);
    } finally {
      setBusy(false);
    }
  });

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <Group justify="space-between" align="baseline">
          <Text c="dimmed">{t('To pay')}</Text>
          <Money value={sheet.net} fz={26} fw={700} />
        </Group>
        <Text size="sm" c="dimmed">
          {t('Earned {{earned}}', { earned: formatNPR(sheet.earned) })}
          {toNumber(sheet.opening_balance) !== 0 &&
            ` ${toNumber(sheet.opening_balance) > 0 ? '+' : '−'} ${t('balance to {{month}}', {
              month: sheet.opening_label,
            })} ${formatNPR(Math.abs(toNumber(sheet.opening_balance)))}`}
          {toNumber(sheet.advances_total) !== 0 &&
            ` − ${t('advances')} ${formatNPR(sheet.advances_total)}`}
        </Text>
        {sheet.notes.map((note) => (
          <Alert key={note} color="blue" p="xs">
            {note}
          </Alert>
        ))}
        <OrderDateField
          label={t('Paid on')}
          value={form.values.paid_on}
          onChange={(ad) => form.setFieldValue('paid_on', ad)}
          error={form.errors.paid_on}
          showHint={false}
        />
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t('Paid by')}
          </Text>
          <SegmentedControl
            fullWidth
            data={PAYMENT_MODES.map((m) => ({ ...m, label: t(m.label) }))}
            {...form.getInputProps('mode')}
          />
        </div>
        <TextInput label={t('Note')} placeholder={t('Optional')} {...form.getInputProps('note')} />
        <Text size="xs" c="dimmed">
          {t(
            'After paying, this month’s attendance and advances are locked. The salary slip opens to print.',
          )}
        </Text>
        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('Pay {{amount}}', { amount: formatNPR(sheet.net) })}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openPaySalary(sheet: MonthSheet, year: number, month: number, label: string) {
  const id = modals.open({
    title: `${sheet.staff.name} · ${label}`,
    children: (
      <PaySalaryForm
        sheet={sheet}
        year={year}
        month={month}
        label={label}
        onDone={() => modals.close(id)}
      />
    ),
  });
}
