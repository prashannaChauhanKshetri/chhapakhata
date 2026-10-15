import {
  ActionIcon,
  Button,
  Card,
  Grid,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconBuildingStore, IconPlus, IconTrash } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { StockItem, Supplier } from '@/api/types';
import { PageHeader } from '@/components/PageHeader';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatNPR, formatQty, todayISO, toNumber } from '@/lib/format';

interface LineValue {
  key: number;
  stock_item: string | null;
  quantity: number | string;
  roll_count: number | string;
  roll_width_ft: number | string;
  roll_length_ft: number | string;
  amount: number | string;
}

let lineKey = 0;
const emptyLine = (): LineValue => ({
  key: lineKey++,
  stock_item: null,
  quantity: '',
  roll_count: 1,
  roll_width_ft: '',
  roll_length_ft: '',
  amount: '',
});

function SupplierForm({ onDone }: { onDone: (s: Supplier | null) => void }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const form = useForm({ initialValues: { name: '', phone: '', address: '', pan_no: '' } });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const supplier = await unwrap(api.POST('/api/v1/suppliers/', { body: values }));
      await client.invalidateQueries({ queryKey: ['suppliers'] });
      onDone(supplier);
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <TextInput label="Supplier name" data-autofocus {...form.getInputProps('name')} />
        <TextInput label="Phone" {...form.getInputProps('phone')} />
        <TextInput label="Address" {...form.getInputProps('address')} />
        <TextInput label="PAN / VAT no." maxLength={9} {...form.getInputProps('pan_no')} />
        <Group justify="flex-end">
          <Button variant="default" onClick={() => onDone(null)}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Add supplier
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export default function PurchaseFormPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const { data: suppliers = [] } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => apiGet<Supplier[]>('/api/v1/suppliers/', { is_active: 'true' }),
  });
  const { data: items = [] } = useQuery({
    queryKey: ['stock-items', { is_active: 'true' }],
    queryFn: () => apiGet<StockItem[]>('/api/v1/stock-items/', { is_active: 'true' }),
  });

  const form = useForm({
    initialValues: {
      supplier: null as string | null,
      purchase_date: todayISO(),
      bill_no: '',
      notes: '',
      lines: [emptyLine()],
    },
    validate: {
      supplier: (v) => (v ? null : t('Choose the supplier')),
      lines: {
        stock_item: (v) => (v ? null : t('Choose the item')),
        amount: (v) => (v === '' ? t('Enter the bill amount') : null),
      },
    },
  });

  const addSupplier = () => {
    const id = modals.open({
      title: t('New supplier'),
      children: (
        <SupplierForm
          onDone={(supplier) => {
            modals.close(id);
            if (supplier) form.setFieldValue('supplier', String(supplier.id));
          }}
        />
      ),
    });
  };

  const total = form.values.lines.reduce((sum, l) => sum + toNumber(l.amount), 0);

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const purchase = await unwrap(
        api.POST('/api/v1/purchases/', {
          body: {
            supplier: Number(values.supplier),
            purchase_date: values.purchase_date,
            bill_no: values.bill_no,
            notes: values.notes,
            lines: values.lines.map((l) => {
              const item = items.find((i) => String(i.id) === l.stock_item);
              return item?.is_roll_media
                ? {
                    stock_item: Number(l.stock_item),
                    amount: String(toNumber(l.amount)),
                    roll_count: toNumber(l.roll_count),
                    roll_width_ft: String(l.roll_width_ft),
                    roll_length_ft: String(l.roll_length_ft),
                  }
                : {
                    stock_item: Number(l.stock_item),
                    amount: String(toNumber(l.amount)),
                    quantity: String(l.quantity),
                  };
            }),
          },
        }),
      );
      await Promise.all(
        ['purchases', 'stock-items', 'rolls', 'dashboard'].map((k) =>
          client.invalidateQueries({ queryKey: [k] }),
        ),
      );
      notifySuccess(t('Purchase {{no}} recorded', { no: purchase.purchase_no }));
      navigate('/purchases');
    } catch (error) {
      handleFormError(error, form, t('Purchase not saved'));
    } finally {
      setBusy(false);
    }
  });

  return (
    <>
      <PageHeader
        back={{ to: '/purchases', label: t('Purchases') }}
        title={t('Record purchase')}
        description={t('Enter what the supplier bill says. Stock increases as soon as you save.')}
      />
      <form onSubmit={submit} noValidate>
        <Stack gap="lg">
          <Card>
            <Grid gap="sm">
              <Grid.Col span={{ base: 12, md: 5 }}>
                <Group gap="xs" align="flex-end" wrap="nowrap">
                  <Select
                    style={{ flex: 1 }}
                    label={t('Supplier')}
                    searchable
                    data={suppliers.map((s) => ({ value: String(s.id), label: s.name }))}
                    {...form.getInputProps('supplier')}
                  />
                  <Tooltip label={t('New supplier')}>
                    <ActionIcon
                      variant="default"
                      size={36}
                      onClick={addSupplier}
                      aria-label={t('New supplier')}
                    >
                      <IconBuildingStore size={18} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Grid.Col>
              <Grid.Col span={{ base: 6, md: 3 }}>
                <DatePickerInput
                  label={t('Bill date')}
                  valueFormat="D MMM YYYY"
                  maxDate={todayISO()}
                  {...form.getInputProps('purchase_date')}
                />
              </Grid.Col>
              <Grid.Col span={{ base: 6, md: 4 }}>
                <TextInput label={t('Supplier bill no.')} {...form.getInputProps('bill_no')} />
              </Grid.Col>
            </Grid>
          </Card>

          <Stack gap="sm">
            {form.values.lines.map((line, i) => {
              const item = items.find((x) => String(x.id) === line.stock_item);
              const sqft =
                toNumber(line.roll_count) *
                toNumber(line.roll_width_ft) *
                toNumber(line.roll_length_ft);
              return (
                <Paper key={line.key} withBorder radius="md" p="md">
                  <Grid gap="sm" align="flex-end">
                    <Grid.Col span={{ base: 12, md: 4 }}>
                      <Select
                        label={t('Item')}
                        searchable
                        data={items.map((x) => ({
                          value: String(x.id),
                          label: `${x.name} (${x.unit_label})`,
                        }))}
                        {...form.getInputProps(`lines.${i}.stock_item`)}
                      />
                    </Grid.Col>
                    {item?.is_roll_media ? (
                      <>
                        <Grid.Col span={{ base: 4, md: 2 }}>
                          <NumberInput
                            label={t('Rolls')}
                            min={1}
                            allowDecimal={false}
                            {...form.getInputProps(`lines.${i}.roll_count`)}
                          />
                        </Grid.Col>
                        <Grid.Col span={{ base: 4, md: 2 }}>
                          <NumberInput
                            label={t('Width ft')}
                            min={0}
                            decimalScale={2}
                            {...form.getInputProps(`lines.${i}.roll_width_ft`)}
                          />
                        </Grid.Col>
                        <Grid.Col span={{ base: 4, md: 2 }}>
                          <NumberInput
                            label={t('Length ft')}
                            min={0}
                            decimalScale={2}
                            {...form.getInputProps(`lines.${i}.roll_length_ft`)}
                          />
                        </Grid.Col>
                      </>
                    ) : (
                      <Grid.Col span={{ base: 12, md: 6 }}>
                        <NumberInput
                          label={
                            item
                              ? t('Quantity ({{unit}})', { unit: item.unit_label })
                              : t('Quantity')
                          }
                          min={0}
                          decimalScale={2}
                          {...form.getInputProps(`lines.${i}.quantity`)}
                        />
                      </Grid.Col>
                    )}
                    <Grid.Col span={{ base: 10, md: 'auto' }}>
                      <NumberInput
                        label={t('Amount (Rs)')}
                        min={0}
                        decimalScale={2}
                        thousandSeparator=","
                        {...form.getInputProps(`lines.${i}.amount`)}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 2, md: 'content' }}>
                      <ActionIcon
                        color="red"
                        size={36}
                        disabled={form.values.lines.length === 1}
                        onClick={() => form.removeListItem('lines', i)}
                        aria-label={t('Remove line')}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Grid.Col>
                  </Grid>
                  {item?.is_roll_media && sqft > 0 && (
                    <Text size="xs" c="dimmed" mt={6}>
                      {t('{{sqft}} sq ft in total', { sqft: formatQty(sqft) })}
                      {toNumber(line.amount) > 0
                        ? ` · Rs ${formatQty(toNumber(line.amount) / sqft)} per sq ft`
                        : ''}
                    </Text>
                  )}
                </Paper>
              );
            })}
            <Button
              variant="default"
              w="fit-content"
              leftSection={<IconPlus size={16} />}
              onClick={() => form.insertListItem('lines', emptyLine())}
            >
              {t('Add line')}
            </Button>
          </Stack>

          <Card>
            <Group justify="space-between" wrap="wrap" gap="sm">
              <TextInput
                placeholder={t('Notes (optional)')}
                style={{ flex: '1 1 260px' }}
                {...form.getInputProps('notes')}
                aria-label={t('Notes')}
              />
              <Group gap="lg">
                <Text fw={600}>
                  {t('Bill total')} {formatNPR(total)}
                </Text>
                <Button type="submit" loading={busy}>
                  {t('Save purchase')}
                </Button>
              </Group>
            </Group>
          </Card>
        </Stack>
      </form>
    </>
  );
}
