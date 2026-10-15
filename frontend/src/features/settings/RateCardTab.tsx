import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Menu,
  NumberInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { modals } from '@mantine/modals';
import { IconDotsVertical, IconHistory, IconPencil, IconPlus } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DataTable } from 'mantine-datatable';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '@/api/client';
import { apiGet } from '@/api/http';
import type { AddOn, MediaType, RateHistory, StockItem } from '@/api/types';
import { SectionCard } from '@/components/SectionCard';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatDateTime, formatQty, toNumber } from '@/lib/format';

import { useAddOns, useMediaTypes } from '../orders/useCatalog';

const BASES = [
  { value: 'fixed', label: 'Fixed amount per item line (e.g. design)' },
  { value: 'per_piece', label: 'Per unit on each piece (e.g. eyelets)' },
  { value: 'per_sqft', label: 'Per sq ft of actual size (e.g. lamination)' },
  { value: 'per_running_ft', label: 'Per running ft of perimeter (e.g. framing)' },
  { value: 'percent', label: 'Percent of print amount (e.g. urgent)' },
];

function useInvalidateCatalog() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['catalog'] });
}

function MediaTypeForm({ media, onDone }: { media?: MediaType; onDone: () => void }) {
  const invalidate = useInvalidateCatalog();
  const [busy, setBusy] = useState(false);
  const { data: materials = [] } = useQuery({
    queryKey: ['stock-items', { kind: 'roll_media' }],
    queryFn: () => apiGet<StockItem[]>('/api/v1/stock-items/', { kind: 'roll_media' }),
  });
  const form = useForm({
    initialValues: {
      name: media?.name ?? '',
      rate_per_sqft: toNumber(media?.rate_per_sqft) || ('' as number | string),
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
      rate_per_sqft: (v) => (v === '' ? 'Enter the rate' : null),
    },
  });
  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    const body = {
      ...values,
      rate_per_sqft: String(values.rate_per_sqft),
      min_sqft: values.min_sqft === '' ? null : String(values.min_sqft),
      material: values.material ? Number(values.material) : null,
    };
    try {
      if (media)
        await unwrap(
          api.PATCH('/api/v1/media-types/{id}/', { params: { path: { id: media.id } }, body }),
        );
      else await unwrap(api.POST('/api/v1/media-types/', { body }));
      await invalidate();
      notifySuccess(media ? 'Media updated' : 'Media added');
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
          data-autofocus
          {...form.getInputProps('name')}
        />
        <Group grow>
          <NumberInput
            label="Rate per sq ft"
            prefix="Rs. "
            min={0}
            decimalScale={2}
            {...form.getInputProps('rate_per_sqft')}
          />
          <NumberInput
            label="Minimum sq ft"
            placeholder="Shop default"
            min={0}
            decimalScale={2}
            {...form.getInputProps('min_sqft')}
          />
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

function AddOnForm({ addon, onDone }: { addon?: AddOn; onDone: () => void }) {
  const invalidate = useInvalidateCatalog();
  const [busy, setBusy] = useState(false);
  const form = useForm({
    initialValues: {
      name: addon?.name ?? '',
      basis: (addon?.basis ?? 'fixed') as string,
      rate: toNumber(addon?.rate) || ('' as number | string),
      default_quantity: toNumber(addon?.default_quantity ?? 1) as number | string,
      description: addon?.description ?? '',
      sort_order: addon?.sort_order ?? 0,
      is_active: addon?.is_active ?? true,
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
      basis: values.basis as 'fixed',
      rate: String(values.rate),
      default_quantity: String(values.default_quantity),
    };
    try {
      if (addon)
        await unwrap(
          api.PATCH('/api/v1/addons/{id}/', { params: { path: { id: addon.id } }, body }),
        );
      else await unwrap(api.POST('/api/v1/addons/', { body }));
      await invalidate();
      notifySuccess(addon ? 'Add-on updated' : 'Add-on added');
      onDone();
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });
  const basis = form.values.basis;
  return (
    <form onSubmit={submit}>
      <Stack gap="sm">
        <TextInput
          label="Name"
          placeholder="e.g. Eyelets"
          data-autofocus
          {...form.getInputProps('name')}
        />
        <Select label="Charged" data={BASES} {...form.getInputProps('basis')} />
        <Group grow>
          <NumberInput
            label={basis === 'percent' ? 'Percent' : 'Rate'}
            prefix={basis === 'percent' ? undefined : 'Rs. '}
            suffix={basis === 'percent' ? ' %' : undefined}
            min={0}
            decimalScale={2}
            {...form.getInputProps('rate')}
          />
          {(basis === 'fixed' || basis === 'per_piece') && (
            <NumberInput
              label="Default quantity"
              description={basis === 'per_piece' ? 'e.g. 8 eyelets per banner' : undefined}
              min={0}
              decimalScale={2}
              {...form.getInputProps('default_quantity')}
            />
          )}
        </Group>
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

function RateHistoryView({ url }: { url: string }) {
  const { data = [], isPending } = useQuery({
    queryKey: ['catalog', 'history', url],
    queryFn: () => apiGet<RateHistory[]>(url),
  });
  if (isPending) return <Text size="sm">Loading…</Text>;
  return (
    <Table verticalSpacing="xs">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>When</Table.Th>
          <Table.Th>By</Table.Th>
          <Table.Th ta="right">Rate</Table.Th>
          <Table.Th ta="right">Min sq ft</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((h) => (
          <Table.Tr key={h.history_id}>
            <Table.Td>
              {formatDateTime(h.history_date)}
              <Text size="xs" c="dimmed">
                {h.history_type}
                {!h.is_active ? ' · not offered' : ''}
              </Text>
            </Table.Td>
            <Table.Td>{h.changed_by ?? '—'}</Table.Td>
            <Table.Td ta="right" className="num">
              {formatAmount(h.rate)}
            </Table.Td>
            <Table.Td ta="right" className="num">
              {h.min_sqft === null ? '—' : formatQty(h.min_sqft)}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

const openForm = (title: string, node: (close: () => void) => React.ReactNode) => {
  const id = modals.open({ title, children: node(() => modals.close(id)) });
};

export function RateCardTab() {
  const { t } = useTranslation();
  const { data: media = [], isPending: mediaLoading } = useMediaTypes();
  const { data: addOns = [], isPending: addOnsLoading } = useAddOns();

  const history = (title: string, url: string) =>
    modals.open({ title, size: 'lg', children: <RateHistoryView url={url} /> });

  return (
    <Stack gap="lg">
      <SectionCard
        title={t('Media types')}
        flush
        actions={
          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={() =>
              openForm(t('New media type'), (close) => <MediaTypeForm onDone={close} />)
            }
          >
            {t('Add media')}
          </Button>
        }
      >
        <DataTable<MediaType>
          minHeight={120}
          fetching={mediaLoading}
          records={media}
          noRecordsText={t('No media types yet')}
          columns={[
            {
              accessor: 'name',
              title: t('Media'),
              render: (m) => (
                <div>
                  <Text size="sm" fw={500}>
                    {m.name}
                  </Text>
                  {m.description && (
                    <Text size="xs" c="dimmed">
                      {m.description}
                    </Text>
                  )}
                </div>
              ),
            },
            {
              accessor: 'rate_per_sqft',
              title: t('Rate / sq ft'),
              textAlign: 'right',
              render: (m) => <span className="num">{formatAmount(m.rate_per_sqft)}</span>,
            },
            {
              accessor: 'effective_min_sqft',
              title: t('Minimum'),
              textAlign: 'right',
              render: (m) => (
                <Text size="sm" className="num" c={m.min_sqft === null ? 'dimmed' : undefined}>
                  {formatQty(m.effective_min_sqft)} sq ft{m.min_sqft === null ? ' *' : ''}
                </Text>
              ),
            },
            {
              accessor: 'material_name',
              title: t('Stock item'),
              visibleMediaQuery: '(min-width: 48em)',
              render: (m) => m.material_name ?? '—',
            },
            {
              accessor: 'is_active',
              title: t('Status'),
              render: (m) =>
                m.is_active ? (
                  <Badge color="green">{t('Offered')}</Badge>
                ) : (
                  <Badge color="slate">{t('Hidden')}</Badge>
                ),
            },
            {
              accessor: 'actions',
              title: '',
              width: 48,
              render: (m) => (
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon aria-label={t('Media actions')}>
                      <IconDotsVertical size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item
                      leftSection={<IconPencil size={16} />}
                      onClick={() =>
                        openForm(t('Edit {{name}}', { name: m.name }), (close) => (
                          <MediaTypeForm media={m} onDone={close} />
                        ))
                      }
                    >
                      {t('Edit')}
                    </Menu.Item>
                    <Menu.Item
                      leftSection={<IconHistory size={16} />}
                      onClick={() =>
                        history(
                          t('Rate history: {{name}}', { name: m.name }),
                          `/api/v1/media-types/${m.id}/history/`,
                        )
                      }
                    >
                      {t('Rate history')}
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              ),
            },
          ]}
        />
        <Text size="xs" c="dimmed" px="lg" py="sm">
          * {t('Uses the shop default minimum (Shop settings).')}
        </Text>
      </SectionCard>

      <SectionCard
        title={t('Add-ons')}
        flush
        actions={
          <Button
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={() => openForm(t('New add-on'), (close) => <AddOnForm onDone={close} />)}
          >
            {t('Add add-on')}
          </Button>
        }
      >
        <DataTable<AddOn>
          minHeight={120}
          fetching={addOnsLoading}
          records={addOns}
          noRecordsText={t('No add-ons yet')}
          columns={[
            {
              accessor: 'name',
              title: t('Add-on'),
              render: (a) => (
                <Text size="sm" fw={500}>
                  {a.name}
                </Text>
              ),
            },
            {
              accessor: 'basis_label',
              title: t('Charged'),
              visibleMediaQuery: '(min-width: 48em)',
            },
            {
              accessor: 'rate',
              title: t('Rate'),
              textAlign: 'right',
              render: (a) => (
                <span className="num">
                  {a.basis === 'percent' ? `${formatQty(a.rate)}%` : formatAmount(a.rate)}
                </span>
              ),
            },
            {
              accessor: 'is_active',
              title: t('Status'),
              render: (a) =>
                a.is_active ? (
                  <Badge color="green">{t('Offered')}</Badge>
                ) : (
                  <Badge color="slate">{t('Hidden')}</Badge>
                ),
            },
            {
              accessor: 'actions',
              title: '',
              width: 48,
              render: (a) => (
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon aria-label={t('Add-on actions')}>
                      <IconDotsVertical size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item
                      leftSection={<IconPencil size={16} />}
                      onClick={() =>
                        openForm(t('Edit {{name}}', { name: a.name }), (close) => (
                          <AddOnForm addon={a} onDone={close} />
                        ))
                      }
                    >
                      {t('Edit')}
                    </Menu.Item>
                    <Menu.Item
                      leftSection={<IconHistory size={16} />}
                      onClick={() =>
                        history(
                          t('Rate history: {{name}}', { name: a.name }),
                          `/api/v1/addons/${a.id}/history/`,
                        )
                      }
                    >
                      {t('Rate history')}
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              ),
            },
          ]}
        />
      </SectionCard>
    </Stack>
  );
}
