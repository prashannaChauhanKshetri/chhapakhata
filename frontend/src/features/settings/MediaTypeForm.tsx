import {
  Button,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { MediaType, StockItem } from '@/api/types';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { toNumber } from '@/lib/format';

/** Refresh rate-card lists everywhere after a change. */
export function useInvalidateCatalog() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['catalog'] });
}

interface MediaTypeFormProps {
  media?: MediaType;
  /** Pre-fills the name of a new item (e.g. what was typed on the order screen). */
  initialName?: string;
  /** Called with the saved item, after the rate card has been refreshed. */
  onSaved?: (media: MediaType) => void;
  onDone: () => void;
}

export function MediaTypeForm({ media, initialName, onSaved, onDone }: MediaTypeFormProps) {
  const invalidate = useInvalidateCatalog();
  const [busy, setBusy] = useState(false);
  const { data: materials = [] } = useQuery({
    queryKey: ['stock-items', { kind: 'roll_media' }],
    queryFn: () => apiGet<StockItem[]>('/api/v1/stock-items/', { kind: 'roll_media' }),
  });
  const form = useForm({
    initialValues: {
      name: media?.name ?? initialName ?? '',
      pricing_unit: (media?.pricing_unit ?? 'sqft') as 'sqft' | 'piece',
      rate: toNumber(media?.rate) || ('' as number | string),
      min_sqft:
        media?.min_sqft === null || media?.min_sqft === undefined
          ? ('' as number | string)
          : toNumber(media.min_sqft),
      material: media?.material ? String(media.material) : null,
      description: media?.description ?? '',
      sort_order: media?.sort_order ?? 0,
      is_active: media?.is_active ?? true,
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Enter a name'),
      rate: (v) => (v === '' ? 'Enter the rate' : null),
    },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const body = {
      ...values,
      rate: String(values.rate),
      min_sqft:
        values.min_sqft === '' || values.pricing_unit === 'piece' ? null : String(values.min_sqft),
      material: values.material ? Number(values.material) : null,
    };
    try {
      const saved = media
        ? await unwrap(
            api.PATCH('/api/v1/media-types/{id}/', { params: { path: { id: media.id } }, body }),
          )
        : await unwrap(api.POST('/api/v1/media-types/', { body }));
      await invalidate();
      notifySuccess(media ? 'Media updated' : `${saved.name} added to the rate card`);
      onSaved?.(saved);
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
        <TextInput
          label="Name"
          placeholder="e.g. Star Flex"
          data-autofocus={initialName ? undefined : true}
          {...form.getInputProps('name')}
        />
        <SegmentedControl
          fullWidth
          data={[
            { value: 'sqft', label: 'Priced per sq ft' },
            { value: 'piece', label: 'Priced per piece' },
          ]}
          {...form.getInputProps('pricing_unit')}
        />
        <Group grow>
          <NumberInput
            label={form.values.pricing_unit === 'piece' ? 'Rate per piece' : 'Rate per sq ft'}
            prefix="Rs. "
            min={0}
            decimalScale={2}
            // When the name came from the order screen, start where typing is needed.
            data-autofocus={initialName ? true : undefined}
            {...form.getInputProps('rate')}
          />
          {form.values.pricing_unit === 'sqft' ? (
            <NumberInput
              label="Minimum sq ft"
              placeholder="Shop default"
              min={0}
              decimalScale={2}
              {...form.getInputProps('min_sqft')}
            />
          ) : (
            <Text size="xs" c="dimmed" mt={24}>
              Size is optional and no minimum applies (e.g. photos, 3D letters, name plates).
            </Text>
          )}
        </Group>
        <Select
          label="Stock item used"
          description="Printing this media deducts from rolls of this item."
          clearable
          data={materials.map((m) => ({ value: String(m.id), label: m.name }))}
          {...form.getInputProps('material')}
        />
        <TextInput label="Description" {...form.getInputProps('description')} />
        <Group grow>
          <NumberInput
            label="Sort order"
            min={0}
            allowDecimal={false}
            {...form.getInputProps('sort_order')}
          />
          <Switch
            mt={26}
            label="Offered"
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />
        </Group>
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

/** Add an item to the rate card from anywhere (e.g. while taking an order). */
export function openMediaTypeModal(options: {
  initialName?: string;
  onSaved?: (media: MediaType) => void;
}) {
  const id = modals.open({
    title: 'Add to the rate card',
    children: (
      <MediaTypeForm
        initialName={options.initialName}
        onSaved={options.onSaved}
        onDone={() => modals.close(id)}
      />
    ),
  });
}
