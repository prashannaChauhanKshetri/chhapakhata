import { Button, Group, Stack, Text, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import type { OrderDetail } from '@/api/types';
import { handleFormError, notifySuccess } from '@/lib/forms';

/** Change the words on an order's items (any status but cancelled). Amounts never change. */
export function EditDetailsForm({ order, onDone }: { order: OrderDetail; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      items: order.items.map((item) => ({
        id: item.id,
        description: item.description ?? '',
        finishing: item.finishing ?? '',
      })),
    },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/orders/{id}/details/', {
          params: { path: { id: order.id } },
          body: values,
        }),
      );
      await client.invalidateQueries({ queryKey: ['order', order.id] });
      await client.invalidateQueries({ queryKey: ['customer', order.customer] });
      notifySuccess(t('Details saved'));
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });

  const billed = order.invoices.some((i) => i.status === 'issued');

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {billed
            ? t(
                'Shown on quotations and statements from now on. The bill already issued keeps the details it was printed with. Amounts do not change.',
              )
            : t(
                'Shown on the quotation, bill and statement. Sizes, quantities and amounts do not change.',
              )}
        </Text>
        {order.items.map((item, index) => (
          <Stack key={item.id} gap={6}>
            <Text size="sm" fw={600}>
              {item.line_no}. {item.media_name}
              {item.has_size ? ` · ${item.size_label}` : ''} × {item.quantity}
            </Text>
            <Group grow align="flex-start" gap="sm">
              <TextInput
                label={t('Details')}
                placeholder={t('e.g. Information board')}
                maxLength={200}
                data-autofocus={index === 0 ? true : undefined}
                {...form.getInputProps(`items.${index}.description`)}
              />
              <TextInput
                label={t('Finishing')}
                placeholder={t('e.g. Hemmed edges, wooden frame')}
                maxLength={200}
                {...form.getInputProps(`items.${index}.finishing`)}
              />
            </Group>
          </Stack>
        ))}
        <Group justify="flex-end" mt="xs">
          <Button variant="default" onClick={onDone}>
            {t('Cancel')}
          </Button>
          <Button type="submit" loading={busy}>
            {t('Save details')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openEditDetails(order: OrderDetail) {
  const id = modals.open({
    title: `Details · ${order.order_no}`,
    size: 'lg',
    children: <EditDetailsForm order={order} onDone={() => modals.close(id)} />,
  });
}
