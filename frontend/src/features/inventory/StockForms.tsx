import {
  ActionIcon,
  Button,
  Group,
  NumberInput,
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
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, unwrap } from '@/api/client';
import type { Roll, StockItem } from '@/api/types';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatQty, toNumber } from '@/lib/format';

const KINDS = [
  { value: 'roll_media', label: 'Roll media (flex, vinyl)' },
  { value: 'ink', label: 'Ink' },
  { value: 'eyelets', label: 'Eyelets / rings' },
  { value: 'frame', label: 'Frame material' },
  { value: 'standee', label: 'Standees' },
  { value: 'other', label: 'Other' },
];
const UNITS = [
  { value: 'sqft', label: 'sq ft' },
  { value: 'litre', label: 'litre' },
  { value: 'box', label: 'box' },
  { value: 'rft', label: 'running ft' },
  { value: 'pcs', label: 'piece' },
];
const DEFAULT_UNIT: Record<string, string> = {
  roll_media: 'sqft',
  ink: 'litre',
  eyelets: 'box',
  frame: 'rft',
  standee: 'pcs',
  other: 'pcs',
};

function useInvalidateStock() {
  const client = useQueryClient();
  return () =>
    Promise.all(
      ['stock-items', 'rolls', 'stock-movements', 'dashboard'].map((k) =>
        client.invalidateQueries({ queryKey: [k] }),
      ),
    );
}

export function StockItemForm({ item, onDone }: { item?: StockItem; onDone: () => void }) {
  const invalidate = useInvalidateStock();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      name: item?.name ?? '',
      kind: (item?.kind ?? 'roll_media') as StockItem['kind'],
      unit: (item?.unit ?? 'sqft') as StockItem['unit'],
      low_stock_level: toNumber(item?.low_stock_level) as number | string,
      notes: item?.notes ?? '',
      is_active: item?.is_active ?? true,
    },
    validate: { name: (v) => (v.trim() ? null : 'Enter a name') },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const body = { ...values, low_stock_level: String(toNumber(values.low_stock_level)) } as never;
    try {
      if (item)
        await unwrap(
          api.PATCH('/api/v1/stock-items/{id}/', { params: { path: { id: item.id } }, body }),
        );
      else await unwrap(api.POST('/api/v1/stock-items/', { body }));
      await invalidate();
      notifySuccess(item ? 'Stock item updated' : 'Stock item added');
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  const isRoll = form.values.kind === 'roll_media';
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <TextInput
          label="Name"
          placeholder="e.g. Star Flex, Eco-solvent ink"
          data-autofocus
          {...form.getInputProps('name')}
        />
        <SimpleGrid cols={2} spacing="sm">
          <Select
            label="Kind"
            data={KINDS}
            {...form.getInputProps('kind')}
            onChange={(v) => {
              form.setFieldValue('kind', (v ?? 'other') as StockItem['kind']);
              form.setFieldValue('unit', DEFAULT_UNIT[v ?? 'other'] as StockItem['unit']);
            }}
          />
          <Select label="Unit" data={UNITS} disabled={isRoll} {...form.getInputProps('unit')} />
        </SimpleGrid>
        <NumberInput
          label="Low-stock level"
          description={
            isRoll
              ? 'Warn when total sq ft across all rolls falls below this.'
              : 'Warn when stock falls below this.'
          }
          min={0}
          decimalScale={2}
          {...form.getInputProps('low_stock_level')}
        />
        <Textarea label="Notes" minRows={1} {...form.getInputProps('notes')} />
        {item && (
          <Switch label="Active" {...form.getInputProps('is_active', { type: 'checkbox' })} />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {item ? 'Save' : 'Add item'}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function OpeningStockForm({ item, onDone }: { item: StockItem; onDone: () => void }) {
  const invalidate = useInvalidateStock();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      quantity: '' as number | string,
      rolls: [
        {
          width_ft: '' as number | string,
          length_ft: '' as number | string,
          remaining_sqft: '' as number | string,
        },
      ],
    },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      await unwrap(
        api.POST('/api/v1/stock-items/{id}/opening/', {
          params: { path: { id: item.id } },
          body: item.is_roll_media
            ? {
                rolls: values.rolls.map((r) => ({
                  width_ft: String(r.width_ft),
                  length_ft: String(r.length_ft),
                  remaining_sqft: r.remaining_sqft === '' ? null : String(r.remaining_sqft),
                })),
              }
            : { quantity: String(values.quantity) },
        }),
      );
      await invalidate();
      notifySuccess('Opening stock added');
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
          Use this once at go-live for stock already in the shop. New stock should be entered as a
          purchase.
        </Text>
        {item.is_roll_media ? (
          <>
            {form.values.rolls.map((roll, i) => (
              <Group key={i} gap="xs" align="flex-end" wrap="nowrap">
                <NumberInput
                  label={i === 0 ? 'Width ft' : undefined}
                  min={0}
                  decimalScale={2}
                  {...form.getInputProps(`rolls.${i}.width_ft`)}
                />
                <NumberInput
                  label={i === 0 ? 'Length ft' : undefined}
                  min={0}
                  decimalScale={2}
                  {...form.getInputProps(`rolls.${i}.length_ft`)}
                />
                <NumberInput
                  label={i === 0 ? 'Sq ft left (if part-used)' : undefined}
                  min={0}
                  decimalScale={2}
                  placeholder={
                    formatQty(toNumber(roll.width_ft) * toNumber(roll.length_ft)) || 'Full roll'
                  }
                  {...form.getInputProps(`rolls.${i}.remaining_sqft`)}
                />
                <ActionIcon
                  color="red"
                  mb={4}
                  disabled={form.values.rolls.length === 1}
                  onClick={() => form.removeListItem('rolls', i)}
                  aria-label="Remove roll"
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            ))}
            <Button
              variant="default"
              size="xs"
              w="fit-content"
              leftSection={<IconPlus size={14} />}
              onClick={() =>
                form.insertListItem('rolls', { width_ft: '', length_ft: '', remaining_sqft: '' })
              }
            >
              Add roll
            </Button>
          </>
        ) : (
          <NumberInput
            label={`Quantity (${item.unit_label})`}
            min={0}
            decimalScale={2}
            data-autofocus
            {...form.getInputProps('quantity')}
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Add opening stock
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

type StockAction = 'adjust' | 'wastage' | 'usage';

export function StockActionForm({
  item,
  action,
  rolls,
  onDone,
}: {
  item: StockItem;
  action: StockAction;
  rolls: Roll[];
  onDone: () => void;
}) {
  const invalidate = useInvalidateStock();
  const [busy, setBusy] = useState(false);
  const activeRolls = rolls.filter((r) => r.status === 'active' || action === 'adjust');
  const form = useForm({
    initialValues: {
      roll: activeRolls[0] ? String(activeRolls[0].id) : '',
      quantity: '' as number | string,
      reason: '',
    },
    validate: {
      roll: (v) => (item.is_roll_media && !v ? 'Choose the roll' : null),
      quantity: (v) =>
        v === '' || (action !== 'adjust' && toNumber(v) <= 0) ? 'Enter a quantity' : null,
      reason: (v) => (action !== 'usage' && !v.trim() ? 'Give a reason' : null),
    },
  });
  const roll = rolls.find((r) => String(r.id) === form.values.roll);
  const current = item.is_roll_media ? roll?.remaining_sqft : item.on_hand;

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const rollId = item.is_roll_media ? Number(values.roll) : null;
    try {
      const path = { params: { path: { id: item.id } } };
      if (action === 'adjust') {
        await unwrap(
          api.POST('/api/v1/stock-items/{id}/adjust/', {
            ...path,
            body: {
              counted_quantity: String(values.quantity),
              reason: values.reason,
              roll: rollId,
            },
          }),
        );
      } else if (action === 'wastage') {
        await unwrap(
          api.POST('/api/v1/stock-items/{id}/wastage/', {
            ...path,
            body: { quantity: String(values.quantity), reason: values.reason, roll: rollId },
          }),
        );
      } else {
        await unwrap(
          api.POST('/api/v1/stock-items/{id}/usage/', {
            ...path,
            body: { quantity: String(values.quantity), reason: values.reason, roll: rollId },
          }),
        );
      }
      await invalidate();
      notifySuccess(
        action === 'adjust'
          ? 'Stock adjusted'
          : action === 'wastage'
            ? 'Wastage recorded'
            : 'Usage recorded',
      );
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });

  const label =
    action === 'adjust'
      ? 'Counted quantity'
      : action === 'wastage'
        ? 'Quantity wasted'
        : 'Quantity used';
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        {item.is_roll_media && (
          <Select
            label="Roll"
            data={activeRolls.map((r) => ({
              value: String(r.id),
              label: `${r.code} · ${formatQty(r.width_ft)} × ${formatQty(r.length_ft)} ft · ${formatQty(r.remaining_sqft)} sq ft left`,
            }))}
            {...form.getInputProps('roll')}
          />
        )}
        <NumberInput
          label={`${label} (${item.unit_label})`}
          description={
            current !== undefined ? `Currently ${formatQty(current)} ${item.unit_label}` : undefined
          }
          min={0}
          decimalScale={2}
          data-autofocus
          {...form.getInputProps('quantity')}
        />
        <TextInput
          label={action === 'usage' ? 'Note (optional)' : 'Reason'}
          placeholder={
            action === 'adjust'
              ? 'e.g. Monthly physical count'
              : action === 'wastage'
                ? 'e.g. Misprint, test print'
                : 'e.g. Ink refill for machine 1'
          }
          {...form.getInputProps('reason')}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Save
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function openStockItemModal(item?: StockItem) {
  const id = modals.open({
    title: item ? `Edit ${item.name}` : 'New stock item',
    children: <StockItemForm item={item} onDone={() => modals.close(id)} />,
  });
}

export function openOpeningStock(item: StockItem) {
  const id = modals.open({
    title: `Opening stock: ${item.name}`,
    size: 'lg',
    children: <OpeningStockForm item={item} onDone={() => modals.close(id)} />,
  });
}

export function openStockAction(item: StockItem, action: StockAction, rolls: Roll[]) {
  const titles = { adjust: 'Adjust after count', wastage: 'Record wastage', usage: 'Record usage' };
  const id = modals.open({
    title: `${titles[action]}: ${item.name}`,
    children: (
      <StockActionForm item={item} action={action} rolls={rolls} onDone={() => modals.close(id)} />
    ),
  });
}
