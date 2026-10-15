import {
  Alert,
  Button,
  Card,
  FileInput,
  Grid,
  Group,
  Image,
  NumberInput,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconInfoCircle, IconUpload } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ensureCsrfCookie } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { ShopSettings } from '@/api/types';
import { PageLoader } from '@/components/PageLoader';
import { SectionCard } from '@/components/SectionCard';
import { handleFormError, notifySuccess } from '@/lib/forms';
import { toNumber } from '@/lib/format';

import { useShopSettings } from '../orders/useCatalog';

type ImageField = 'logo' | 'stamp_image' | 'signature_image';
const IMAGE_FIELDS: { key: ImageField; label: string; hint: string }[] = [
  {
    key: 'logo',
    label: 'Logo',
    hint: 'Top-left of every document. PNG with transparent background works best.',
  },
  {
    key: 'stamp_image',
    label: 'Stamp',
    hint: 'Printed over the signature area of invoices and quotations.',
  },
  { key: 'signature_image', label: 'Signature', hint: 'Authorised signature for invoices.' },
];

function ShopForm({ shop }: { shop: ShopSettings }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<Partial<Record<ImageField, File | null>>>({});
  const [remove, setRemove] = useState<Partial<Record<ImageField, boolean>>>({});
  const form = useForm({
    initialValues: {
      name: shop.name,
      tagline: shop.tagline ?? '',
      address: shop.address ?? '',
      phone: shop.phone ?? '',
      email: shop.email ?? '',
      pan_vat_number: shop.pan_vat_number ?? '',
      is_vat_registered: shop.is_vat_registered ?? false,
      vat_rate: toNumber(shop.vat_rate) as number | string,
      default_min_sqft: toNumber(shop.default_min_sqft) as number | string,
      round_total_to_rupee: shop.round_total_to_rupee ?? false,
      front_desk_max_discount_percent: toNumber(shop.front_desk_max_discount_percent) as
        | number
        | string,
      invoice_footer_note: shop.invoice_footer_note ?? '',
      quotation_validity_days: shop.quotation_validity_days ?? 7,
      quotation_terms: shop.quotation_terms ?? '',
      order_number_pattern: shop.order_number_pattern ?? '',
      job_number_pattern: shop.job_number_pattern ?? '',
      invoice_number_pattern: shop.invoice_number_pattern ?? '',
      receipt_number_pattern: shop.receipt_number_pattern ?? '',
      purchase_number_pattern: shop.purchase_number_pattern ?? '',
    },
    validate: { name: (v) => (v.trim() ? null : t('Enter the shop name')) },
  });

  const submit = form.onSubmit(async (values) => {
    setBusy(true);
    try {
      const body = new FormData();
      Object.entries(values).forEach(([k, v]) => body.append(k, String(v)));
      IMAGE_FIELDS.forEach(({ key }) => {
        const file = files[key];
        if (file) body.append(key, file);
        if (remove[key]) body.append(`remove_${key}`, 'true');
      });
      const response = await fetch('/api/v1/settings/shop/', {
        method: 'PATCH',
        body,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': await ensureCsrfCookie() },
      });
      if (!response.ok) throw await ApiError.fromResponse(response);
      await client.invalidateQueries({ queryKey: ['settings', 'shop'] });
      setFiles({});
      setRemove({});
      notifySuccess(t('Shop settings saved'));
    } catch (error) {
      handleFormError(error, form);
    } finally {
      setBusy(false);
    }
  });

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="lg">
        <SectionCard title={t('Shop identity')}>
          <Grid gap="sm">
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput label={t('Shop name')} {...form.getInputProps('name')} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput label={t('Tagline')} {...form.getInputProps('tagline')} />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput label={t('Address')} {...form.getInputProps('address')} />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 3 }}>
              <TextInput label={t('Phone')} {...form.getInputProps('phone')} />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 3 }}>
              <TextInput label={t('Email')} {...form.getInputProps('email')} />
            </Grid.Col>
          </Grid>
        </SectionCard>

        <SectionCard title={t('Tax and pricing')}>
          <Grid gap="sm">
            <Grid.Col span={{ base: 12, md: 4 }}>
              <TextInput
                label={t('PAN / VAT number')}
                maxLength={20}
                {...form.getInputProps('pan_vat_number')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 4 }}>
              <Switch
                mt={{ base: 0, md: 30 }}
                label={t('VAT registered')}
                description={t('Adds VAT to quotations and invoices')}
                {...form.getInputProps('is_vat_registered', { type: 'checkbox' })}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 4 }}>
              <NumberInput
                label={t('VAT rate %')}
                min={0}
                max={100}
                decimalScale={2}
                disabled={!form.values.is_vat_registered}
                {...form.getInputProps('vat_rate')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 4 }}>
              <NumberInput
                label={t('Default minimum sq ft')}
                description={t('Smaller items are charged as this size')}
                min={0}
                decimalScale={2}
                {...form.getInputProps('default_min_sqft')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 6, md: 4 }}>
              <NumberInput
                label={t('Front desk discount limit %')}
                min={0}
                max={100}
                decimalScale={2}
                {...form.getInputProps('front_desk_max_discount_percent')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 4 }}>
              <Switch
                mt={{ base: 0, md: 30 }}
                label={t('Round totals to the rupee')}
                {...form.getInputProps('round_total_to_rupee', { type: 'checkbox' })}
              />
            </Grid.Col>
          </Grid>
          <Alert color="slate" variant="light" mt="md" icon={<IconInfoCircle size={16} />}>
            {t(
              'Rate changes apply to new orders only. Quoted and confirmed orders keep their rates.',
            )}
          </Alert>
        </SectionCard>

        <SectionCard title={t('Documents')}>
          <Grid gap="md">
            {IMAGE_FIELDS.map(({ key, label, hint }) => {
              const current = shop[key];
              return (
                <Grid.Col key={key} span={{ base: 12, md: 4 }}>
                  <Stack gap={6}>
                    <FileInput
                      label={t(label)}
                      description={t(hint)}
                      accept="image/png,image/jpeg,image/webp"
                      placeholder={current ? t('Replace image') : t('Choose image')}
                      leftSection={<IconUpload size={16} />}
                      clearable
                      value={files[key] ?? null}
                      onChange={(file) => setFiles((f) => ({ ...f, [key]: file }))}
                    />
                    {current && !remove[key] && (
                      <Group gap="sm">
                        <Image
                          src={current}
                          alt={label}
                          h={48}
                          w="auto"
                          fit="contain"
                          radius="sm"
                          bg="slate.0"
                          p={4}
                        />
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="red"
                          onClick={() => setRemove((r) => ({ ...r, [key]: true }))}
                        >
                          {t('Remove')}
                        </Button>
                      </Group>
                    )}
                    {remove[key] && (
                      <Text size="xs" c="red.7">
                        {t('Will be removed when you save.')}
                      </Text>
                    )}
                  </Stack>
                </Grid.Col>
              );
            })}
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput
                label={t('Invoice footer note')}
                {...form.getInputProps('invoice_footer_note')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <NumberInput
                label={t('Quotation valid for (days)')}
                min={1}
                max={90}
                allowDecimal={false}
                {...form.getInputProps('quotation_validity_days')}
              />
            </Grid.Col>
            <Grid.Col span={12}>
              <Textarea label={t('Quotation terms')} {...form.getInputProps('quotation_terms')} />
            </Grid.Col>
          </Grid>
        </SectionCard>

        <SectionCard title={t('Document numbers')}>
          <Text size="sm" c="dimmed" mb="sm">
            {t(
              'Use {n} for the running number, {n:04d} for zero-padding and {fy} for the fiscal year (e.g. 2083/84). Invoice and receipt numbers restart each fiscal year.',
            )}
          </Text>
          <Grid gap="sm">
            {(
              [
                ['order_number_pattern', 'Orders'],
                ['job_number_pattern', 'Jobs'],
                ['invoice_number_pattern', 'Invoices'],
                ['receipt_number_pattern', 'Receipts'],
                ['purchase_number_pattern', 'Purchases'],
              ] as const
            ).map(([key, label]) => (
              <Grid.Col key={key} span={{ base: 12, sm: 6, md: 4 }}>
                <TextInput label={t(label)} ff="monospace" {...form.getInputProps(key)} />
              </Grid.Col>
            ))}
          </Grid>
        </SectionCard>

        <Card padding="md">
          <Group justify="flex-end">
            <Button type="submit" loading={busy}>
              {t('Save settings')}
            </Button>
          </Group>
        </Card>
      </Stack>
    </form>
  );
}

export function ShopSettingsTab() {
  const { data } = useShopSettings();
  if (!data) return <PageLoader />;
  return <ShopForm key={data.updated_at} shop={data} />;
}
