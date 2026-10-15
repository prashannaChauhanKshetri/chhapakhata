import {
  Alert,
  Button,
  Checkbox,
  Divider,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconCircleCheck, IconPrinter } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import type { components } from '@/api/schema';
import type { OrderDetail } from '@/api/types';

type PaymentInput = components['schemas']['PaymentInputRequest'];
import { handleFormError, notifyError } from '@/lib/forms';
import { formatNPR, toNumber } from '@/lib/format';
import { WALLETS } from '@/lib/status';

const MODES = [
  { value: 'cash', label: 'Cash' },
  { value: 'wallet', label: 'QR / Wallet' },
  { value: 'bank', label: 'Bank' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'credit', label: 'Credit (udhar)' },
];

/** Counter checkout: invoice, take payment or put on credit, then mark delivered. */
export function DeliverForm({ order, onDone }: { order: OrderDetail; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<OrderDetail | null>(null);
  const balance = toNumber(order.total) - toNumber(order.paid_amount);
  const hasInvoice = !!order.invoice_no;

  const form = useForm({
    initialValues: {
      issue_invoice: !hasInvoice,
      mode: balance > 0 ? 'cash' : 'credit',
      amount: balance > 0 ? balance : 0,
      wallet: '',
      bank_name: '',
      reference_no: '',
      cheque_no: '',
      cheque_date: null as string | null,
    },
    validate: {
      amount: (v, values) =>
        values.mode !== 'credit' && toNumber(v) <= 0 ? t('Enter the amount received') : null,
      wallet: (v, values) => (values.mode === 'wallet' && !v ? t('Choose the wallet') : null),
      bank_name: (v, values) =>
        ['bank', 'cheque'].includes(values.mode) && !v.trim() ? t('Enter the bank name') : null,
      cheque_no: (v, values) =>
        values.mode === 'cheque' && !v.trim() ? t('Enter the cheque number') : null,
      cheque_date: (v, values) =>
        values.mode === 'cheque' && !v ? t('Enter the cheque date') : null,
    },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const payment: PaymentInput | null =
        values.mode === 'credit' || toNumber(values.amount) <= 0
          ? null
          : {
              amount: String(values.amount),
              mode: values.mode as PaymentInput['mode'],
              wallet:
                values.mode === 'wallet'
                  ? (values.wallet as NonNullable<PaymentInput['wallet']>)
                  : '',
              bank_name: values.bank_name,
              reference_no: values.reference_no,
              cheque_no: values.cheque_no,
              cheque_date: values.mode === 'cheque' ? values.cheque_date : null,
            };
      const updated = await unwrap(
        api.POST('/api/v1/orders/{id}/deliver/', {
          params: { path: { id: order.id } },
          body: { issue_invoice: values.issue_invoice, payment },
        }),
      );
      await Promise.all(
        [
          'order',
          'orders',
          'jobs',
          'board',
          'dashboard',
          'invoices',
          'payments',
          'customer',
          'customers',
        ].map((k) => client.invalidateQueries({ queryKey: [k] })),
      );
      setResult(updated);
    } catch (error) {
      handleFormError(error, form, t('Could not deliver'));
    } finally {
      setBusy(false);
    }
  });

  if (result) {
    const invoice = result.invoices.find((i) => i.status === 'issued');
    const print = (size: string) =>
      openFile(`/api/v1/invoices/${invoice!.id}/print/?size=${size}`, { method: 'POST' }).catch(
        (e) => notifyError(e),
      );
    const left = toNumber(result.total) - toNumber(result.paid_amount);
    return (
      <Stack gap="md">
        <Alert color="green" icon={<IconCircleCheck size={18} />} title={t('Delivered')}>
          {left > 0
            ? t("{{amount}} is added to the customer's dues.", { amount: formatNPR(left) })
            : t('Fully paid. Thank you!')}
        </Alert>
        {invoice && (
          <>
            <Text size="sm" fw={500}>
              {t('Print invoice {{no}}', { no: invoice.invoice_no })}
            </Text>
            <Group gap="xs">
              <Button
                variant="default"
                leftSection={<IconPrinter size={16} />}
                onClick={() => void print('80mm')}
              >
                3-inch
              </Button>
              <Button
                variant="default"
                leftSection={<IconPrinter size={16} />}
                onClick={() => void print('a5')}
              >
                A5
              </Button>
              <Button
                variant="default"
                leftSection={<IconPrinter size={16} />}
                onClick={() => void print('a4')}
              >
                A4
              </Button>
            </Group>
          </>
        )}
        <Group justify="flex-end">
          <Button onClick={onDone}>{t('Done')}</Button>
        </Group>
      </Stack>
    );
  }

  const mode = form.values.mode;
  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <SimpleGrid cols={3} spacing="xs">
          <div>
            <Text size="xs" c="dimmed">
              {t('Total')}
            </Text>
            <Text fw={600}>{formatNPR(order.total)}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed">
              {t('Paid')}
            </Text>
            <Text fw={600}>{formatNPR(order.paid_amount)}</Text>
          </div>
          <div>
            <Text size="xs" c="dimmed">
              {t('Balance')}
            </Text>
            <Text fw={600} c={balance > 0 ? 'red.7' : undefined}>
              {formatNPR(balance)}
            </Text>
          </div>
        </SimpleGrid>
        <Divider />
        {hasInvoice ? (
          <Text size="sm" c="dimmed">
            {t('Invoice {{no}} is already issued.', { no: order.invoice_no })}
          </Text>
        ) : (
          <Checkbox
            label={t('Issue the tax invoice now')}
            description={t("Recommended. The invoice adds this order to the customer's ledger.")}
            {...form.getInputProps('issue_invoice', { type: 'checkbox' })}
          />
        )}
        {balance > 0 && (
          <>
            <Text size="sm" fw={500}>
              {t('Payment now')}
            </Text>
            <SegmentedControl
              fullWidth
              data={MODES.map((m) => ({ ...m, label: t(m.label) }))}
              {...form.getInputProps('mode')}
            />
            {mode === 'credit' ? (
              <Text size="sm" c="dimmed">
                {t("Nothing is collected now. The balance stays as the customer's due.")}
              </Text>
            ) : (
              <NumberInput
                label={t('Amount received')}
                prefix="Rs. "
                thousandSeparator=","
                decimalScale={2}
                min={0}
                description={
                  toNumber(form.values.amount) < balance
                    ? t('The rest is added to dues.')
                    : undefined
                }
                {...form.getInputProps('amount')}
              />
            )}
            {mode === 'wallet' && (
              <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
                <Select label={t('Wallet / QR')} data={WALLETS} {...form.getInputProps('wallet')} />
                <TextInput
                  label={t('Transaction reference')}
                  {...form.getInputProps('reference_no')}
                />
              </SimpleGrid>
            )}
            {mode === 'bank' && (
              <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
                <TextInput label={t('Bank name')} {...form.getInputProps('bank_name')} />
                <TextInput label={t('Reference number')} {...form.getInputProps('reference_no')} />
              </SimpleGrid>
            )}
            {mode === 'cheque' && (
              <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm">
                <TextInput label={t('Cheque number')} {...form.getInputProps('cheque_no')} />
                <TextInput label={t('Bank name')} {...form.getInputProps('bank_name')} />
                <DatePickerInput
                  label={t('Cheque date')}
                  valueFormat="D MMM YYYY"
                  {...form.getInputProps('cheque_date')}
                />
              </SimpleGrid>
            )}
          </>
        )}
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('Mark delivered')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openDeliver(order: OrderDetail) {
  const id = modals.open({
    title: `Deliver ${order.order_no}`,
    size: 'lg',
    children: <DeliverForm order={order} onDone={() => modals.close(id)} />,
  });
}
