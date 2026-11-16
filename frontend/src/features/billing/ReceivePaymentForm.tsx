import {
  Alert,
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconCircleCheck, IconPrinter } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { Customer, OrderList, Paginated, Payment } from '@/api/types';
import { handleFormError, notifyError } from '@/lib/forms';
import { formatNPR, todayISO, toNumber } from '@/lib/format';
import { PAYMENT_MODES, WALLETS } from '@/lib/status';

import { CustomerSelect } from '../customers/CustomerSelect';

interface ReceivePaymentFormProps {
  customer?: Customer | null;
  orderId?: number | null;
  suggestedAmount?: string | number;
  /** A payment entered wrongly: the form starts from it and saves a correction. */
  correcting?: Payment | null;
  onDone: (payment: Payment | null) => void;
}

export function ReceivePaymentForm({
  customer: initialCustomer,
  orderId,
  suggestedAmount,
  correcting,
  onDone,
}: ReceivePaymentFormProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  // The picker only needs the id, name and phone that a payment carries.
  const [customer, setCustomer] = useState<Customer | null>(
    initialCustomer ?? (correcting ? (correcting.customer as Customer) : null),
  );
  const [saved, setSaved] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false);

  const form = useForm({
    initialValues: correcting
      ? {
          order: correcting.order ? String(correcting.order.id) : '',
          amount: toNumber(correcting.amount) as number | string,
          mode: correcting.mode as string,
          wallet: correcting.wallet ?? '',
          bank_name: correcting.bank_name ?? '',
          reference_no: correcting.reference_no ?? '',
          cheque_no: correcting.cheque_no ?? '',
          cheque_date: (correcting.cheque_date ?? null) as string | null,
          payment_date: correcting.payment_date,
          notes: correcting.notes ?? '',
          reason: '',
        }
      : {
          order: orderId ? String(orderId) : '',
          amount: (suggestedAmount ? toNumber(suggestedAmount) : '') as number | string,
          mode: 'cash' as string,
          wallet: '',
          bank_name: '',
          reference_no: '',
          cheque_no: '',
          cheque_date: null as string | null,
          payment_date: todayISO(),
          notes: '',
          reason: '',
        },
    validate: {
      amount: (v) => (toNumber(v) > 0 ? null : t('Enter the amount received')),
      wallet: (v, values) =>
        values.mode === 'wallet' && !v ? t('Choose the wallet or QR app') : null,
      // A correction may keep an old (imported) payment's missing cheque or bank details.
      bank_name: (v, values) =>
        !correcting && ['bank', 'cheque'].includes(values.mode) && !v.trim()
          ? t('Enter the bank name')
          : null,
      cheque_no: (v, values) =>
        !correcting && values.mode === 'cheque' && !v.trim() ? t('Enter the cheque number') : null,
      cheque_date: (v, values) =>
        !correcting && values.mode === 'cheque' && !v ? t('Enter the cheque date') : null,
      reason: (v) =>
        correcting && v.trim().length < 5
          ? t('Write what was wrong (at least 5 characters)')
          : null,
    },
  });

  const { data: orders } = useQuery({
    queryKey: ['orders', 'payable', customer?.id],
    queryFn: () =>
      apiGet<Paginated<OrderList>>('/api/v1/orders/', {
        customer: customer!.id,
        has_balance: 'true',
        page_size: 50,
        ordering: '-created_at',
      }),
    enabled: !!customer,
  });

  const submit = form.onSubmit(async (values) => {
    if (!customer) {
      notifyError(new Error(t('Choose the customer first.')));
      return;
    }
    setBusy(true);
    const body = {
      customer: customer.id,
      order: values.order ? Number(values.order) : null,
      amount: String(values.amount),
      mode: values.mode as 'cash',
      wallet: values.mode === 'wallet' ? (values.wallet as 'esewa') : ('' as const),
      bank_name: values.bank_name,
      reference_no: values.reference_no,
      cheque_no: values.cheque_no,
      cheque_date: values.mode === 'cheque' ? values.cheque_date : null,
      payment_date: values.payment_date,
      notes: values.notes,
    };
    try {
      const payment = correcting
        ? await unwrap(
            api.POST('/api/v1/payments/{id}/correct/', {
              params: { path: { id: correcting.id } },
              body: { ...body, reason: values.reason },
            }),
          )
        : await unwrap(api.POST('/api/v1/payments/', { body }));
      await Promise.all([
        client.invalidateQueries({ queryKey: ['payments'] }),
        client.invalidateQueries({ queryKey: ['orders'] }),
        client.invalidateQueries({ queryKey: ['order'] }),
        client.invalidateQueries({ queryKey: ['customers'] }),
        client.invalidateQueries({ queryKey: ['customer'] }),
        client.invalidateQueries({ queryKey: ['dashboard'] }),
      ]);
      setSaved(payment);
    } catch (error) {
      handleFormError(error, form, t('Payment not saved'));
    } finally {
      setBusy(false);
    }
  });

  const print = (size: 'a5' | '80mm') =>
    openFile(`/api/v1/payments/${saved!.id}/receipt/?size=${size}`).catch((e) =>
      notifyError(e, t('Could not open receipt')),
    );

  if (saved) {
    return (
      <Stack gap="md">
        <Alert
          color="green"
          icon={<IconCircleCheck size={18} />}
          title={correcting ? t('Payment corrected') : t('Payment saved')}
        >
          {correcting
            ? t(
                'Receipt {{no}} for {{amount}} from {{name}} replaces {{old}}, which is now void.',
                {
                  no: saved.receipt_no,
                  amount: formatNPR(saved.amount),
                  name: saved.customer.name,
                  old: correcting.receipt_no,
                },
              )
            : t('Receipt {{no}} for {{amount}} from {{name}}.', {
                no: saved.receipt_no,
                amount: formatNPR(saved.amount),
                name: saved.customer.name,
              })}
        </Alert>
        <Group justify="flex-end" gap="xs">
          <Button
            variant="default"
            leftSection={<IconPrinter size={16} />}
            onClick={() => void print('80mm')}
          >
            {t('3-inch receipt')}
          </Button>
          <Button
            variant="default"
            leftSection={<IconPrinter size={16} />}
            onClick={() => void print('a5')}
          >
            {t('A5 receipt')}
          </Button>
          <Button onClick={() => onDone(saved)}>{t('Done')}</Button>
        </Group>
      </Stack>
    );
  }

  const mode = form.values.mode;
  const orderOptions = [...(orders?.results ?? [])];
  const selectedOrder = orderOptions.find((o) => String(o.id) === form.values.order);

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <CustomerSelect
          value={customer}
          disabled={!!initialCustomer}
          onChange={(c) => {
            setCustomer(c);
            form.setFieldValue('order', '');
          }}
        />
        <Select
          label={t('For order')}
          description={t('Leave empty to receive money on account (towards old dues).')}
          placeholder={customer ? t('On account') : t('Choose a customer first')}
          disabled={!customer}
          clearable
          data={[
            ...orderOptions.map((o) => ({
              value: String(o.id),
              label: `${o.order_no} · ${t('balance')} ${formatNPR(o.balance_due)}`,
            })),
            // The corrected payment's own order, even if it is now fully paid.
            ...(correcting?.order &&
            correcting.customer.id === customer?.id &&
            !orderOptions.some((o) => o.id === correcting.order!.id)
              ? [{ value: String(correcting.order.id), label: correcting.order.order_no }]
              : []),
          ]}
          {...form.getInputProps('order')}
          onChange={(v) => {
            form.setFieldValue('order', v ?? '');
            const o = orders?.results.find((x) => String(x.id) === v);
            if (o && !form.values.amount) form.setFieldValue('amount', toNumber(o.balance_due));
          }}
        />
        <NumberInput
          label={t('Amount received')}
          prefix="Rs. "
          thousandSeparator=","
          decimalScale={2}
          min={0}
          required
          data-autofocus
          description={
            selectedOrder
              ? `${t('Order balance')}: ${formatNPR(selectedOrder.balance_due)}`
              : undefined
          }
          {...form.getInputProps('amount')}
        />
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t('Payment mode')}
          </Text>
          <SegmentedControl
            fullWidth
            data={PAYMENT_MODES.map((m) => ({ ...m, label: t(m.label) }))}
            {...form.getInputProps('mode')}
          />
        </div>
        {mode === 'wallet' && (
          <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
            <Select
              label={t('Wallet / QR')}
              data={WALLETS}
              required
              {...form.getInputProps('wallet')}
            />
            <TextInput label={t('Transaction reference')} {...form.getInputProps('reference_no')} />
          </SimpleGrid>
        )}
        {mode === 'bank' && (
          <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
            <TextInput label={t('Bank name')} required {...form.getInputProps('bank_name')} />
            <TextInput label={t('Reference number')} {...form.getInputProps('reference_no')} />
          </SimpleGrid>
        )}
        {mode === 'cheque' && (
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm">
            <TextInput label={t('Cheque number')} required {...form.getInputProps('cheque_no')} />
            <TextInput label={t('Bank name')} required {...form.getInputProps('bank_name')} />
            <DatePickerInput
              label={t('Cheque date')}
              required
              valueFormat="D MMM YYYY"
              {...form.getInputProps('cheque_date')}
            />
          </SimpleGrid>
        )}
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <DatePickerInput
            label={t('Payment date')}
            valueFormat="D MMM YYYY"
            maxDate={todayISO()}
            {...form.getInputProps('payment_date')}
          />
          <Textarea label={t('Note')} minRows={1} {...form.getInputProps('notes')} />
        </SimpleGrid>
        {correcting && (
          <Textarea
            label={t('What was wrong?')}
            description={t(
              'Receipt {{no}} will be voided (kept on record) and a corrected receipt saved.',
              { no: correcting.receipt_no },
            )}
            required
            minRows={2}
            {...form.getInputProps('reason')}
          />
        )}
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={() => onDone(null)}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {correcting ? t('Save correction') : t('Save payment')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openReceivePayment(
  options: Omit<ReceivePaymentFormProps, 'onDone'> & { onDone?: (p: Payment | null) => void },
) {
  const id = modals.open({
    title: 'Receive payment',
    size: 'lg',
    children: (
      <ReceivePaymentForm
        {...options}
        onDone={(payment) => {
          modals.close(id);
          options.onDone?.(payment);
        }}
      />
    ),
  });
}

/** Fix a payment entered wrongly (owner): the form starts from it. */
export function openCorrectPayment(payment: Payment, onDone?: (p: Payment | null) => void) {
  const id = modals.open({
    title: `Correct receipt ${payment.receipt_no}`,
    size: 'lg',
    children: (
      <ReceivePaymentForm
        correcting={payment}
        onDone={(saved) => {
          modals.close(id);
          onDone?.(saved);
        }}
      />
    ),
  });
}
