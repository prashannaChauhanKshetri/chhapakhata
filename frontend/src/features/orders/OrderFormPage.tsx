import {
  Alert,
  Box,
  Button,
  Card,
  Grid,
  Group,
  NumberInput,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  Textarea,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { useDebouncedValue, useHotkeys } from '@mantine/hooks';
import { IconAlertCircle, IconCheck, IconDeviceFloppy, IconPlus } from '@tabler/icons-react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { ApiError } from '@/api/errors';
import { apiGet } from '@/api/http';
import type { Customer, CustomerRate, OrderDetail, PricePreview } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatNPR, formatQty, toNumber } from '@/lib/format';

import { CustomerSelect } from '../customers/CustomerSelect';
import { ItemRow } from './ItemRow';
import classes from './OrderForm.module.css';
import {
  emptyItem,
  initialValues,
  isItemComplete,
  orderPayload,
  type OrderFormValues,
  pricingPayload,
} from './orderForm';
import { useAddOns, useMediaTypes, useShopSettings } from './useCatalog';

/** Per-piece rows may leave both width and height empty. `path` is e.g. "items.2.width". */
function perPieceAt(values: OrderFormValues, path: string): boolean {
  return values.items[Number(path.split('.')[1])]?.per_piece ?? false;
}

function otherSide(values: OrderFormValues, path: string) {
  const [, index, side] = path.split('.');
  const item = values.items[Number(index)];
  return side === 'width' ? item?.height : item?.width;
}

function OrderFormInner({
  order,
  presetCustomer,
}: {
  order?: OrderDetail;
  presetCustomer?: Customer | null;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user } = useAuth();
  const isEdit = !!order;
  const [customer, setCustomer] = useState<Customer | null>(presetCustomer ?? null);
  const [saving, setSaving] = useState<null | 'quotation' | 'confirm'>(null);
  const { data: mediaTypes = [] } = useMediaTypes();
  const { data: addOns = [] } = useAddOns();
  const { data: shop } = useShopSettings();

  const form = useForm<OrderFormValues>({
    initialValues: initialValues(order),
    validate: {
      items: {
        media_type: (v) => (v ? null : t('Choose a media')),
        width: (v, values, path) =>
          toNumber(v) > 0 || (perPieceAt(values, path) && !toNumber(otherSide(values, path)))
            ? null
            : t('Enter width'),
        height: (v, values, path) =>
          toNumber(v) > 0 || (perPieceAt(values, path) && !toNumber(otherSide(values, path)))
            ? null
            : t('Enter height'),
        quantity: (v) => (toNumber(v) >= 1 ? null : t('At least 1')),
      },
    },
  });

  // What this customer paid last time for each item, offered as the default rate.
  const { data: customerRates = [] } = useQuery({
    queryKey: ['customer', customer?.id, 'rates'],
    queryFn: () => apiGet<CustomerRate[]>(`/api/v1/customers/${customer!.id}/rates/`),
    enabled: !!customer,
    staleTime: 60_000,
  });
  const lastRates = useMemo(
    () => Object.fromEntries(customerRates.map((r) => [String(r.media_type), r])),
    [customerRates],
  );

  // Live pricing: the server is the only calculator, so the screen always matches the bill.
  const pricing = useMemo(() => pricingPayload(form.values), [form.values]);
  const [debouncedPricing] = useDebouncedValue(pricing, 250);
  const preview = useQuery({
    queryKey: ['price-preview', order?.id ?? null, customer?.id ?? null, debouncedPricing],
    queryFn: () =>
      unwrap(
        api.POST('/api/v1/orders/price-preview/', {
          body: { ...debouncedPricing, order: order?.id ?? null, customer: customer?.id ?? null },
        }),
      ),
    enabled: debouncedPricing.items.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: 30_000,
  });

  // Map preview results back to form rows (only complete rows are priced).
  const resultsByIndex = useMemo(() => {
    const map: Record<number, PricePreview['items'][number]> = {};
    if (!preview.data || preview.isPlaceholderData) return map;
    let i = 0;
    form.values.items.forEach((item, index) => {
      if (isItemComplete(item)) map[index] = preview.data.items[i++];
    });
    return map;
  }, [preview.data, preview.isPlaceholderData, form.values.items]);

  const totals = preview.data?.totals;
  const discountLimit = preview.data?.discount_limit ?? user?.discount_limit ?? null;
  const previewError = preview.error instanceof ApiError ? preview.error : null;

  const addItem = () => {
    const last = form.values.items[form.values.items.length - 1];
    form.insertListItem('items', emptyItem(last?.unit ?? 'ft', null));
  };

  const save = async (mode: 'quotation' | 'confirm') => {
    const validation = form.validate();
    if (!customer) {
      form.setFieldError('customer', t('Choose the customer'));
      return;
    }
    if (validation.hasErrors) return;
    setSaving(mode);
    try {
      const body = orderPayload(form.values, customer.id, mode === 'confirm');
      const saved = isEdit
        ? await unwrap(
            api.PUT('/api/v1/orders/{id}/', { params: { path: { id: order.id } }, body }),
          )
        : await unwrap(api.POST('/api/v1/orders/', { body }));
      await client.invalidateQueries({ queryKey: ['orders'] });
      await client.invalidateQueries({ queryKey: ['order', saved.id] });
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      notifySuccess(
        isEdit
          ? t('Order {{no}} updated', { no: saved.order_no })
          : mode === 'confirm'
            ? t('Order {{no}} confirmed', { no: saved.order_no })
            : t('Quotation {{no}} saved', { no: saved.order_no }),
      );
      navigate(`/orders/${saved.id}`, { replace: true });
    } catch (error) {
      handleFormError(error, form, t('Order not saved'));
    } finally {
      setSaving(null);
    }
  };

  const primary: 'quotation' | 'confirm' = isEdit ? 'quotation' : 'confirm';
  useHotkeys([['mod+S', () => void save(primary)]], []);

  const discountType = form.values.discount_type;

  const summary = (
    <Card className={classes.summary}>
      <Stack gap="sm">
        <Text fw={600}>{t('Summary')}</Text>
        <div className={classes.summaryRow}>
          <Text size="sm" c="dimmed">
            {t('Items')}
          </Text>
          <Text size="sm">
            {form.values.items.length} ·{' '}
            {formatQty(
              preview.data?.items.reduce((s, i) => s + toNumber(i.total_billable_sqft), 0) ?? 0,
            )}{' '}
            sq ft
          </Text>
        </div>
        <div className={classes.summaryRow}>
          <Text size="sm" c="dimmed">
            {t('Sub-total')}
          </Text>
          <Text size="sm" className="num">
            {formatAmount(totals?.subtotal)}
          </Text>
        </div>

        <Stack gap={6}>
          <Group justify="space-between" gap="xs">
            <Text size="sm" c="dimmed">
              {t('Discount')}
            </Text>
            <SegmentedControl
              size="xs"
              data={[
                { value: 'none', label: t('None') },
                { value: 'percent', label: '%' },
                { value: 'amount', label: 'Rs' },
              ]}
              {...form.getInputProps('discount_type')}
            />
          </Group>
          {discountType !== 'none' && (
            <NumberInput
              size="sm"
              min={0}
              decimalScale={2}
              suffix={discountType === 'percent' ? ' %' : undefined}
              prefix={discountType === 'amount' ? 'Rs. ' : undefined}
              thousandSeparator=","
              description={
                discountLimit !== null
                  ? t('Your limit: {{limit}}% of sub-total', { limit: formatQty(discountLimit) })
                  : undefined
              }
              aria-label={t('Discount value')}
              {...form.getInputProps('discount_value')}
            />
          )}
          {toNumber(totals?.discount_amount) > 0 && (
            <div className={classes.summaryRow}>
              <Text size="sm" c="dimmed">
                {t('Discount amount')}
              </Text>
              <Text size="sm" className="num">
                − {formatAmount(totals?.discount_amount)}
              </Text>
            </div>
          )}
        </Stack>

        {toNumber(totals?.vat_rate) > 0 && (
          <>
            <div className={classes.summaryRow}>
              <Text size="sm" c="dimmed">
                {t('Taxable amount')}
              </Text>
              <Text size="sm" className="num">
                {formatAmount(totals?.taxable_amount)}
              </Text>
            </div>
            <div className={classes.summaryRow}>
              <Text size="sm" c="dimmed">
                {t('VAT {{rate}}%', { rate: formatQty(totals?.vat_rate) })}
              </Text>
              <Text size="sm" className="num">
                {formatAmount(totals?.vat_amount)}
              </Text>
            </div>
          </>
        )}
        {toNumber(totals?.round_off) !== 0 && (
          <div className={classes.summaryRow}>
            <Text size="sm" c="dimmed">
              {t('Round off')}
            </Text>
            <Text size="sm" className="num">
              {formatAmount(totals?.round_off)}
            </Text>
          </div>
        )}
        <div className={classes.total}>
          <Text fw={600}>{t('Total')}</Text>
          <Text fz={22} fw={600}>
            {formatNPR(totals?.total)}
          </Text>
        </div>
        {!shop?.is_vat_registered && (
          <Text size="xs" c="dimmed">
            {t('VAT is not added: the shop is set as PAN-only.')}
          </Text>
        )}
        {previewError && (
          <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />} p="xs">
            <Text size="xs">{previewError.summary}</Text>
          </Alert>
        )}

        <Stack gap="xs" mt="xs">
          {isEdit ? (
            <Button
              leftSection={<IconDeviceFloppy size={16} />}
              loading={saving === 'quotation'}
              onClick={() => void save('quotation')}
            >
              {t('Save changes')}
            </Button>
          ) : (
            <>
              <Button
                leftSection={<IconCheck size={16} />}
                loading={saving === 'confirm'}
                disabled={!!saving}
                onClick={() => void save('confirm')}
              >
                {t('Confirm order')}
              </Button>
              <Button
                variant="default"
                loading={saving === 'quotation'}
                disabled={!!saving}
                onClick={() => void save('quotation')}
              >
                {t('Save as quotation')}
              </Button>
            </>
          )}
          <Text size="xs" c="dimmed" ta="center">
            {t('Ctrl + S saves · Enter on the last item adds another')}
          </Text>
        </Stack>
      </Stack>
    </Card>
  );

  return (
    <>
      <PageHeader
        back={
          isEdit
            ? { to: `/orders/${order.id}`, label: order.order_no }
            : { to: '/orders', label: t('Orders') }
        }
        title={isEdit ? t('Edit {{no}}', { no: order.order_no }) : t('New order')}
        description={
          isEdit
            ? t('Lines you keep stay at the rate they were quoted.')
            : t('Price by size: sq ft × rate, with the minimum charge and add-ons.')
        }
      />
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack gap="lg">
            <Card>
              <CustomerSelect
                value={customer}
                disabled={isEdit}
                error={form.errors.customer}
                onChange={(c) => {
                  setCustomer(c);
                  form.clearFieldError('customer');
                }}
              />
              {customer && toNumber(customer.balance) > 0 && (
                <Text size="xs" c="red.7" mt={6}>
                  {t('This customer already owes {{amount}}.', {
                    amount: formatNPR(customer.balance),
                  })}
                </Text>
              )}
            </Card>

            <Stack gap="sm">
              {form.values.items.map((item, index) => (
                <ItemRow
                  key={item.key}
                  form={form}
                  index={index}
                  mediaTypes={mediaTypes}
                  addOns={addOns}
                  result={resultsByIndex[index]}
                  lastRates={lastRates}
                  canRemove={form.values.items.length > 1}
                  isLast={index === form.values.items.length - 1}
                  onEnterLast={addItem}
                />
              ))}
              <Button
                variant="default"
                leftSection={<IconPlus size={16} />}
                onClick={addItem}
                w="fit-content"
              >
                {t('Add another item')}
              </Button>
            </Stack>

            <Card>
              <Grid gap="sm">
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <DateTimePicker
                    label={t('Deliver by')}
                    valueFormat="ddd D MMM YYYY, h:mm A"
                    clearable
                    {...form.getInputProps('deadline')}
                  />
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Switch
                    mt={{ base: 0, sm: 30 }}
                    label={t('Urgent job')}
                    description={t('Shown first on the production board')}
                    {...form.getInputProps('is_urgent', { type: 'checkbox' })}
                  />
                </Grid.Col>
                <Grid.Col span={12}>
                  <Textarea
                    label={t('Notes')}
                    placeholder={t('Anything the designer or printer should know')}
                    {...form.getInputProps('notes')}
                  />
                </Grid.Col>
              </Grid>
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>{summary}</Grid.Col>
      </Grid>
      <Box className={classes.mobileBar}>
        <div>
          <Text size="xs" c="dimmed">
            {t('Total')}
          </Text>
          <Text fw={600}>{formatNPR(totals?.total)}</Text>
        </div>
        <Button loading={!!saving} onClick={() => void save(primary)}>
          {isEdit ? t('Save') : t('Confirm order')}
        </Button>
      </Box>
    </>
  );
}

export default function OrderFormPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const presetCustomerId = params.get('customer');
  const orderQuery = useQuery({
    queryKey: ['order', Number(id)],
    queryFn: () => apiGet<OrderDetail>(`/api/v1/orders/${id}/`),
    enabled: !!id,
  });
  const customerQuery = useQuery({
    queryKey: ['customer', Number(presetCustomerId)],
    queryFn: () => apiGet<Customer>(`/api/v1/customers/${presetCustomerId}/`),
    enabled: !id && !!presetCustomerId,
  });
  const editCustomerQuery = useQuery({
    queryKey: ['customer', orderQuery.data?.customer.id],
    queryFn: () => apiGet<Customer>(`/api/v1/customers/${orderQuery.data!.customer.id}/`),
    enabled: !!orderQuery.data,
  });
  const ready = id
    ? !!orderQuery.data && !!editCustomerQuery.data
    : !presetCustomerId || !customerQuery.isPending;

  if (orderQuery.error)
    return <QueryError error={orderQuery.error} onRetry={() => void orderQuery.refetch()} />;
  if (!ready) return <PageLoader />;
  return (
    <OrderFormInner
      key={id ?? 'new'}
      order={orderQuery.data}
      presetCustomer={id ? editCustomerQuery.data : customerQuery.data}
    />
  );
}
