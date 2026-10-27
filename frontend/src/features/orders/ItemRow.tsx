import {
  ActionIcon,
  Badge,
  Box,
  Chip,
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
import {
  IconChevronDown,
  IconChevronRight,
  IconCopy,
  IconPlus,
  IconSettings,
  IconTrash,
} from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import type { AddOn, CustomerRate, ItemResult, MediaType } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { formatAmount, formatQty, toNumber } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { UNITS } from '@/lib/status';

import { openMediaTypeModal } from '../settings/MediaTypeForm';
import classes from './OrderForm.module.css';
import { newKey, type OrderFormValues } from './orderForm';

const ADD_MEDIA = '__add_media__';
const OPEN_RATE_CARD = '__open_rate_card__';

interface ItemRowProps {
  form: UseFormReturnType<OrderFormValues>;
  index: number;
  mediaTypes: MediaType[];
  addOns: AddOn[];
  result?: ItemResult;
  /** The customer's last rate for each media id, if they bought it before. */
  lastRates: Record<string, CustomerRate>;
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
  lastRates,
  canRemove,
  onEnterLast,
  isLast,
}: ItemRowProps) {
  const { t } = useTranslation();
  const item = form.values.items[index];
  const { can } = useAuth();
  const navigate = useNavigate();
  const [mediaSearch, setMediaSearch] = useState('');
  const [moreOpen, setMoreOpen] = useState(
    Boolean(item.finishing || item.design_file_ref || item.description),
  );
  const path = (field: string) => `items.${index}.${field}`;
  const media = mediaTypes.find((m) => String(m.id) === item.media_type);

  const mediaOptions = mediaTypes
    .filter((m) => m.is_active || String(m.id) === item.media_type)
    .map((m) => ({
      value: String(m.id),
      label: `${m.name} · Rs ${formatQty(m.rate)}/${m.pricing_unit === 'piece' ? 'piece' : 'sq ft'}`,
    }));
  const last = item.media_type ? lastRates[item.media_type] : undefined;
  const perUnit = item.per_piece ? t('piece') : t('sq ft');
  const rateSource = result?.rate_source;

  const applyMedia = (chosen: MediaType | undefined) => {
    const value = chosen ? String(chosen.id) : null;
    form.setFieldValue(path('media_type'), value);
    form.setFieldValue(path('per_piece'), chosen?.pricing_unit === 'piece');
    // A returning customer gets the rate they paid last time; staff can switch back.
    const previous = value ? lastRates[value] : undefined;
    form.setFieldValue(path('rate'), previous ? toNumber(previous.last_rate) : '');
  };

  // Something not on the rate card yet: the owner can add it without leaving the order.
  const typed = mediaSearch.trim();
  const canAddMedia = can(Perm.CATALOG_MANAGE);
  const exists = mediaTypes.some((m) => m.name.toLowerCase() === typed.toLowerCase());
  const showAdd =
    canAddMedia && typed.length >= 2 && !exists && !mediaOptions.some((o) => o.label === typed);
  const selectData = [
    ...mediaOptions,
    ...(showAdd
      ? [{ value: ADD_MEDIA, label: t('Add “{{name}}” to the rate card', { name: typed }) }]
      : []),
    ...(canAddMedia ? [{ value: OPEN_RATE_CARD, label: t('Open rate card…') }] : []),
  ];

  const chooseMedia = (value: string | null) => {
    if (value === ADD_MEDIA) {
      openMediaTypeModal({ initialName: typed, onSaved: (created) => applyMedia(created) });
      return;
    }
    if (value === OPEN_RATE_CARD) {
      navigate('/settings/rate-card');
      return;
    }
    applyMedia(mediaTypes.find((m) => String(m.id) === value));
  };

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
            data={selectData}
            searchable
            searchValue={mediaSearch}
            onSearchChange={setMediaSearch}
            nothingFoundMessage={
              canAddMedia ? undefined : t('Not on the rate card. Ask the owner to add it.')
            }
            renderOption={({ option }) =>
              option.value === ADD_MEDIA || option.value === OPEN_RATE_CARD ? (
                <Group gap={6} wrap="nowrap" c="orange.8">
                  {option.value === ADD_MEDIA ? <IconPlus size={15} /> : <IconSettings size={15} />}
                  <Text size="sm" fw={500} c="inherit">
                    {option.label}
                  </Text>
                </Group>
              ) : (
                option.label
              )
            }
            {...form.getInputProps(path('media_type'))}
            onChange={chooseMedia}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <NumberInput
            label={item.per_piece ? t('Width (optional)') : t('Width')}
            min={0}
            decimalScale={2}
            {...form.getInputProps(path('width'))}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3, lg: 2 }}>
          <NumberInput
            label={item.per_piece ? t('Height (optional)') : t('Height')}
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

        <Grid.Col span={{ base: 12, sm: 5, lg: 4 }}>
          <NumberInput
            label={t('Rate per {{unit}}', { unit: perUnit })}
            prefix="Rs. "
            min={0}
            decimalScale={2}
            placeholder={media ? formatAmount(media.rate) : undefined}
            description={
              rateSource === 'previous'
                ? t("Customer's last rate")
                : rateSource === 'custom'
                  ? t('Custom rate')
                  : media
                    ? t('Rate card')
                    : undefined
            }
            inputWrapperOrder={['label', 'input', 'description', 'error']}
            {...form.getInputProps(path('rate'))}
          />
          {media && (
            <Group gap={6} mt={6}>
              <Chip
                size="xs"
                variant="outline"
                checked={rateSource === 'card' || item.rate === ''}
                onChange={() => form.setFieldValue(path('rate'), '')}
              >
                {t('Card Rs {{rate}}', { rate: formatQty(result?.card_rate ?? media.rate) })}
              </Chip>
              {last && (
                <Tooltip
                  label={t('{{order}} on {{date}} BS · bought {{n}} times', {
                    order: last.order_no,
                    date: last.order_date_bs,
                    n: last.times,
                  })}
                >
                  <Chip
                    size="xs"
                    variant="outline"
                    checked={rateSource === 'previous'}
                    onChange={() => form.setFieldValue(path('rate'), toNumber(last.last_rate))}
                  >
                    {t('Last time Rs {{rate}}', { rate: formatQty(last.last_rate) })}
                  </Chip>
                </Tooltip>
              )}
            </Group>
          )}
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 7, lg: 8 }}>
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
              {result.pricing_unit === 'piece' ? (
                <>
                  {result.quantity} {result.quantity === 1 ? t('piece') : t('pieces')} × Rs{' '}
                  {formatQty(result.rate)}
                </>
              ) : (
                <>
                  {formatQty(result.sqft)} sq ft
                  {result.quantity > 1
                    ? ` × ${result.quantity} = ${formatQty(result.total_sqft)} sq ft`
                    : ''}
                  {' · '}
                  {formatQty(result.total_billable_sqft)} × Rs {formatQty(result.rate)}
                </>
              )}
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
            {!media
              ? t('Choose a media to start.')
              : item.per_piece
                ? t('Enter the quantity to see the price.')
                : t('Enter width and height to see the price.')}
          </Text>
        )}
      </Box>
    </Paper>
  );
}
