import {
  Alert,
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import type { components } from '@/api/schema';
import type { MonthSheet, Staff } from '@/api/types';
import { Money } from '@/components/Money';
import { handleFormError, notifyError, notifySuccess } from '@/lib/forms';
import { formatNPR, todayISO, toNumber } from '@/lib/format';
import { PAYMENT_MODES } from '@/lib/status';

const day = (v: unknown) => (v ? String(v).slice(0, 10) : null);

// -- Add or edit a worker -------------------------------------------------------------

function StaffForm({ staff, onDone }: { staff?: Staff; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      name: staff?.name ?? '',
      job_title: staff?.job_title ?? '',
      phone: staff?.phone ?? '',
      monthly_salary: (staff ? toNumber(staff.monthly_salary) : '') as number | string,
      joined_on: staff?.joined_on ?? todayISO(),
      is_active: staff?.is_active ?? true,
      left_on: (staff?.left_on ?? null) as string | null,
      notes: staff?.notes ?? '',
    },
    validate: {
      name: (v) => (v.trim() ? null : t('Enter the name')),
      monthly_salary: (v) => (v === '' || toNumber(v) < 0 ? t('Enter the monthly salary') : null),
      left_on: (v, values) => (!values.is_active && !v ? t('Enter the last working day') : null),
    },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const body = {
      ...values,
      monthly_salary: String(values.monthly_salary),
      left_on: values.is_active ? values.left_on || null : values.left_on,
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

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <TextInput label={t('Name')} required data-autofocus {...form.getInputProps('name')} />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <TextInput
            label={t('Work')}
            placeholder={t('e.g. Designer, Fitter')}
            {...form.getInputProps('job_title')}
          />
          <TextInput label={t('Phone')} {...form.getInputProps('phone')} />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <NumberInput
            label={t('Monthly salary (Rs)')}
            required
            min={0}
            thousandSeparator=","
            decimalScale={2}
            {...form.getInputProps('monthly_salary')}
          />
          <DatePickerInput
            label={t('Joined on')}
            valueFormat="D MMM YYYY"
            {...form.getInputProps('joined_on')}
            onChange={(v) => form.setFieldValue('joined_on', day(v) ?? todayISO())}
          />
        </SimpleGrid>
        {staff && (
          <Switch
            label={t('Still working here')}
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
        )}
        {staff && !form.values.is_active && (
          <DatePickerInput
            label={t('Last working day')}
            description={t('No pay is counted after this day.')}
            valueFormat="D MMM YYYY"
            required
            {...form.getInputProps('left_on')}
            onChange={(v) => form.setFieldValue('left_on', day(v))}
          />
        )}
        <Textarea label={t('Notes')} {...form.getInputProps('notes')} />
        {staff && (
          <Text size="xs" c="dimmed">
            {t('A new salary counts from months not yet paid. Paid months keep what was paid.')}
          </Text>
        )}
        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {staff ? t('Save') : t('Add staff')}
          </Button>
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
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <NumberInput
            label={t('Amount (Rs)')}
            required
            min={0}
            thousandSeparator=","
            decimalScale={2}
            data-autofocus
            {...form.getInputProps('amount')}
          />
          <DatePickerInput
            label={t('Given on')}
            valueFormat="D MMM YYYY"
            maxDate={todayISO()}
            {...form.getInputProps('date')}
            onChange={(v) => form.setFieldValue('date', day(v) ?? todayISO())}
          />
        </SimpleGrid>
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
          {t('Earned {{earned}} − advances {{advances}}', {
            earned: formatNPR(sheet.earned),
            advances: formatNPR(sheet.advances_total),
          })}
        </Text>
        {sheet.days_ahead > 0 && (
          <Alert color="amber" p="xs">
            {t(
              '{{month}} is not over: the {{n}} days still to come count as present. Pay at month end to be exact.',
              { month: label, n: sheet.days_ahead },
            )}
          </Alert>
        )}
        {sheet.notes.map((note) => (
          <Alert key={note} color="blue" p="xs">
            {note}
          </Alert>
        ))}
        <DatePickerInput
          label={t('Paid on')}
          valueFormat="D MMM YYYY"
          maxDate={todayISO()}
          {...form.getInputProps('paid_on')}
          onChange={(v) => form.setFieldValue('paid_on', day(v) ?? todayISO())}
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
