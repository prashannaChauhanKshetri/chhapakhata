import {
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
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import type { Customer } from '@/api/types';
import { handleFormError, notifySuccess } from '@/lib/forms';

interface CustomerFormProps {
  customer?: Customer;
  initialName?: string;
  onSaved: (customer: Customer) => void;
  onCancel: () => void;
}

export function CustomerForm({ customer, initialName, onSaved, onCancel }: CustomerFormProps) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const isNew = !customer;
  const form = useForm({
    initialValues: {
      name: customer?.name ?? initialName ?? '',
      phone: customer?.phone ?? '',
      alt_phone: customer?.alt_phone ?? '',
      address: customer?.address ?? '',
      pan_no: customer?.pan_no ?? '',
      customer_type: (customer?.customer_type ?? 'individual') as 'individual' | 'business',
      notes: customer?.notes ?? '',
      is_active: customer?.is_active ?? true,
      opening_balance: 0 as number | string,
    },
    validate: {
      name: (v) => (v.trim().length >= 2 ? null : t("Enter the customer's name")),
      pan_no: (v) => (!v || /^\d{9}$/.test(v) ? null : t('PAN / VAT numbers have 9 digits')),
      phone: (v) => (!v || /^[0-9+\-\s]{6,20}$/.test(v) ? null : t('Enter a valid phone number')),
    },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const { opening_balance, ...rest } = values;
      const saved = isNew
        ? await unwrap(
            api.POST('/api/v1/customers/', {
              body: { ...rest, opening_balance: String(opening_balance || 0) },
            }),
          )
        : await unwrap(
            api.PATCH('/api/v1/customers/{id}/', {
              params: { path: { id: customer.id } },
              body: rest,
            }),
          );
      await client.invalidateQueries({ queryKey: ['customers'] });
      await client.invalidateQueries({ queryKey: ['customer', saved.id] });
      notifySuccess(isNew ? t('Customer added') : t('Customer updated'));
      onSaved(saved);
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="sm">
        <SegmentedControl
          data={[
            { value: 'individual', label: t('Individual') },
            { value: 'business', label: t('Business / Organisation') },
          ]}
          {...form.getInputProps('customer_type')}
        />
        <TextInput label={t('Name')} required data-autofocus {...form.getInputProps('name')} />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <TextInput label={t('Phone')} inputMode="tel" {...form.getInputProps('phone')} />
          <TextInput
            label={t('Alternate phone')}
            inputMode="tel"
            {...form.getInputProps('alt_phone')}
          />
        </SimpleGrid>
        <TextInput label={t('Address')} {...form.getInputProps('address')} />
        <TextInput
          label={t('PAN / VAT number')}
          description={t("Printed on invoices as the buyer's PAN")}
          inputMode="numeric"
          maxLength={9}
          {...form.getInputProps('pan_no')}
        />
        {isNew && (
          <NumberInput
            label={t('Existing balance (optional)')}
            description={t(
              'Amount the customer already owes. Enter a negative number for an advance they have with you.',
            )}
            prefix="Rs. "
            thousandSeparator=","
            decimalScale={2}
            {...form.getInputProps('opening_balance')}
          />
        )}
        <Textarea label={t('Notes')} {...form.getInputProps('notes')} />
        {!isNew && (
          <Switch
            label={t('Active')}
            description={t('Inactive customers are hidden when taking new orders.')}
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
        )}
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onCancel}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {isNew ? t('Add customer') : t('Save changes')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openCustomerModal(options: {
  customer?: Customer;
  initialName?: string;
  onSaved?: (customer: Customer) => void;
}) {
  const id = modals.open({
    title: options.customer ? 'Edit customer' : 'New customer',
    size: 'lg',
    children: (
      <CustomerForm
        customer={options.customer}
        initialName={options.initialName}
        onCancel={() => modals.close(id)}
        onSaved={(customer) => {
          modals.close(id);
          options.onSaved?.(customer);
        }}
      />
    ),
  });
}

export function CustomerTypeText({ type }: { type: string }) {
  return (
    <Text size="xs" c="dimmed">
      {type === 'business' ? 'Business' : 'Individual'}
    </Text>
  );
}
