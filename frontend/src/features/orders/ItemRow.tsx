import {
  ActionIcon,
  Badge,
  Box,
  Collapse,
  Grid,
  Group,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import type { UseFormReturnType } from '@mantine/form';
import { IconChevronDown, IconChevronRight, IconCopy, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { AddOn, ItemResult, MediaType } from '@/api/types';
import { formatAmount, formatQty, toNumber } from '@/lib/format';
import { UNITS } from '@/lib/status';

import classes from './OrderForm.module.css';
import { newKey, type OrderFormValues } from './orderForm';

interface ItemRowProps {
  form: UseFormReturnType<OrderFormValues>;
  index: number;
  mediaTypes: MediaType[];
  addOns: AddOn[];
  result?: ItemResult;
  canRemove: boolean;
  onEnterLast: () => void;
  isLast: boolean;
}

export function ItemRow({
  form,
  index,
  mediaTypes,
  addOns,
  result,
  canRemove,
  onEnterLast,
  isLast,
}: ItemRowProps) {
  const { t } = useTranslation();
  const item = form.values.items[index];
  const [moreOpen, setMoreOpen] = useState(
    Boolean(item.finishing || item.design_file_ref || item.description),
  );
  const path = (field: string) => `items.${index}.${field}`;
  const media = mediaTypes.find((m) => String(m.id) === item.media_type);

  const mediaOptions = mediaTypes
    .filter((m) => m.is_active || String(m.id) === item.media_type)
    .map((m) => ({
      value: String(m.id),
      label: `${m.name} · Rs ${formatQty(m.rate_per_sqft)}/sq ft`,
    }));

  const activeAddOns = addOns.filter(
    (a) => a.is_active || item.addons.some((x) => x.addon === String(a.id)),
  );

  const setAddOns = (ids: string[]) => {
    const next = ids.map((id) => {
      const existing = item.addons.find((a) => a.addon === id);
      const def = addOns.find((a) => String(a.id) === id);
      return existing ?? { addon: id, quantity: toNumber(def?.default_quantity ?? 1) };
    });
    form.setFieldValue(path('addons'), next);
  };

  const duplicate = () => {
    form.insertListItem(
      'items',
      { ...item, key: newKey(), id: null, addons: item.addons.map((a) => ({ ...a })) },
      index + 1,
    );
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && isLast && (event.target as HTMLElement).tagName === 'INPUT') {
      event.preventDefault();
      onEnterLast();
    }
  };

  return (
    <Paper withBorder radius="md" p="md" className={classes.item} onKeyDown={onKeyDown}>
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <Group gap="xs">
          <Text size="sm" fw={600} c="slate.7">
            {t('Item {{n}}', { n: index + 1 })}
          </Text>
          {result?.min_applied && (
            <Tooltip
              label={t('Smaller than the minimum, so it is charged as {{min}} sq ft per piece.', {
                min: formatQty(result.min_sqft),
              })}
            >
              <Badge color="amber" size="sm">
                {t('Min. {{min}} sq ft', { min: formatQty(result.min_sqft) })}
              </Badge>
            </Tooltip>
          )}
        </Group>
        <Group gap={2}>
          <Tooltip label={t('Duplicate item')}>
            <ActionIcon onClick={duplicate} aria-label={t('Duplicate item')}>
              <IconCopy size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label={t('Remove item')}>
            <ActionIcon
              color="red"
              disabled={!canRemove}
              onClick={() => form.removeListItem('items', index)}
              aria-label={t('Remove item')}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Grid gap="sm" align="flex-start">
        <Grid.Col span={{ base: 12, sm: 12, lg: 4 }}>
          <Select
            label={t('Media')}
            placeholder={t('Choose material')}
            data={mediaOptions}
            searchable
            {...form.getInputProps(path('media_type'))}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <NumberInput
            label={t('Width')}
            min={0}
            decimalScale={2}
            {...form.getInputProps(path('width'))}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <NumberInput
            label={t('Height')}
            min={0}
            decimalScale={2}
            {...form.getInputProps(path('height'))}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <Select label={t('Unit')} data={UNITS} {...form.getInputProps(path('unit'))} />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <NumberInput
            label={t('Qty')}
            min={1}
            allowDecimal={false}
            {...form.getInputProps(path('quantity'))}
          />
        </Grid.Col>

        <Grid.Col span={12}>
          <MultiSelect
            label={t('Add-ons')}
            placeholder={
              item.addons.length ? undefined : t('Design, eyelets, framing, lamination…')
            }
            data={activeAddOns.map((a) => ({
              value: String(a.id),
              label: `${a.name} (${a.basis_label.toLowerCase()})`,
            }))}
            value={item.addons.map((a) => a.addon)}
            onChange={setAddOns}
            clearable
            searchable
          />
          {item.addons.some((a) => addOns.find((x) => String(x.id) === a.addon)?.uses_quantity) && (
            <Group gap="sm" mt="xs">
              {item.addons.map((a, ai) => {
                const def = addOns.find((x) => String(x.id) === a.addon);
                if (!def?.uses_quantity) return null;
                return (
                  <NumberInput
                    key={a.addon}
                    size="xs"
                    w={150}
                    min={0}
                    decimalScale={2}
                    label={
                      def.basis === 'per_piece'
                        ? t('{{name}} per piece', { name: def.name })
                        : t('{{name}} qty', { name: def.name })
                    }
                    {...form.getInputProps(`${path('addons')}.${ai}.quantity`)}
                  />
                );
              })}
            </Group>
          )}
        </Grid.Col>
      </Grid>

      <UnstyledButton onClick={() => setMoreOpen((o) => !o)} mt="sm" className={classes.moreToggle}>
        <Group gap={4}>
          {moreOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          <Text size="xs" c="dimmed" fw={500}>
            {t('Description, finishing and design file')}
          </Text>
        </Group>
      </UnstyledButton>
      <Collapse expanded={moreOpen}>
        <Grid gap="sm" mt={4}>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <TextInput
              label={t('Description')}
              placeholder={t('e.g. Shop signboard')}
              {...form.getInputProps(path('description'))}
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <TextInput
              label={t('Finishing')}
              placeholder={t('e.g. Hemmed edges, wooden frame')}
              {...form.getInputProps(path('finishing'))}
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <TextInput
              label={t('Design file')}
              placeholder={t('File name or folder (.cdr, .psd)')}
              {...form.getInputProps(path('design_file_ref'))}
            />
          </Grid.Col>
        </Grid>
      </Collapse>

      <Box className={classes.itemResult}>
        {result ? (
          <Group justify="space-between" gap="xs" wrap="wrap">
            <Text size="sm" c="dimmed" className="num">
              {formatQty(result.sqft)} sq ft
              {result.quantity > 1
                ? ` × ${result.quantity} = ${formatQty(result.total_sqft)} sq ft`
                : ''}
              {' · '}
              {formatQty(result.total_billable_sqft)} × Rs {formatQty(result.rate)}
              {toNumber(result.addons_amount) > 0
                ? ` + add-ons ${formatAmount(result.addons_amount)}`
                : ''}
            </Text>
            <Text size="sm" fw={600} className="num">
              Rs. {formatAmount(result.line_total)}
            </Text>
          </Group>
        ) : (
          <Text size="sm" c="dimmed">
            {media ? t('Enter width and height to see the price.') : t('Choose a media to start.')}
          </Text>
        )}
      </Box>
    </Paper>
  );
}
