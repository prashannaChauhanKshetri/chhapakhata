import { Alert, Anchor, Button, Card, Grid, Group, Menu, Stack, Table, Text } from '@mantine/core';
import { IconBan, IconChevronDown, IconPrinter, IconReceipt2 } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { Customer, InvoiceDetail } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { DualDate } from '@/components/DualDate';
import { KeyValue } from '@/components/KeyValue';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';
import { openReasonModal } from '@/components/ReasonModal';
import { SectionCard } from '@/components/SectionCard';
import { StatusBadge } from '@/components/StatusBadge';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatDateTime, formatQty, toNumber } from '@/lib/format';
import { Perm } from '@/lib/permissions';
import { INVOICE_STATUS } from '@/lib/status';

import { openReceivePayment } from './ReceivePaymentForm';

export default function InvoiceDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { can } = useAuth();
  const client = useQueryClient();
  const {
    data: invoice,
    error,
    refetch,
  } = useQuery({
    queryKey: ['invoices', Number(id)],
    queryFn: () => apiGet<InvoiceDetail>(`/api/v1/invoices/${id}/`),
  });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  if (!invoice) return <PageLoader />;
  const cancelled = invoice.status === 'cancelled';

  const print = async (size: 'a4' | 'a5' | '80mm') => {
    try {
      await openFile(`/api/v1/invoices/${invoice.id}/print/?size=${size}`, { method: 'POST' });
      await client.invalidateQueries({ queryKey: ['invoices'] });
    } catch (err) {
      notifyError(err, t('Could not print'));
    }
  };

  const cancel = () =>
    openReasonModal({
      title: t('Cancel invoice {{no}}', { no: invoice.invoice_no }),
      message: t(
        'The invoice stays on record with its number and is marked CANCELLED. The amount is reversed in the customer ledger. The order can then be edited and invoiced again.',
      ),
      confirmLabel: t('Cancel invoice'),
      onConfirm: async (reason) => {
        await unwrap(
          api.POST('/api/v1/invoices/{id}/cancel/', {
            params: { path: { id: invoice.id } },
            body: { reason },
          }),
        );
        await Promise.all(
          ['invoices', 'order', 'orders', 'customer', 'dashboard'].map((k) =>
            client.invalidateQueries({ queryKey: [k] }),
          ),
        );
        notifySuccess(t('Invoice cancelled'));
      },
    });

  const receive = async () => {
    const customer = await apiGet<Customer>(`/api/v1/customers/${invoice.customer}/`);
    openReceivePayment({
      customer,
      orderId: invoice.order.id,
      suggestedAmount: invoice.order_balance,
    });
  };

  return (
    <>
      <PageHeader
        back={{ to: '/invoices', label: t('Invoices') }}
        title={invoice.invoice_no}
        badge={<StatusBadge value={invoice.status} map={INVOICE_STATUS} />}
        description={`${invoice.is_vat_invoice ? t('Tax invoice') : t('Invoice')} · ${t('Fiscal year')} ${invoice.fiscal_year}`}
        actions={
          <>
            {!cancelled && can(Perm.PAYMENTS_RECEIVE) && toNumber(invoice.order_balance) > 0 && (
              <Button
                variant="default"
                leftSection={<IconReceipt2 size={16} />}
                onClick={() => void receive()}
              >
                {t('Receive payment')}
              </Button>
            )}
            {can(Perm.DOCUMENTS_ISSUE) && (
              <Menu position="bottom-end">
                <Menu.Target>
                  <Button
                    leftSection={<IconPrinter size={16} />}
                    rightSection={<IconChevronDown size={14} />}
                  >
                    {invoice.print_count > 0 ? t('Print copy') : t('Print')}
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item onClick={() => void print('a4')}>{t('A4 invoice')}</Menu.Item>
                  <Menu.Item onClick={() => void print('a5')}>{t('A5 invoice')}</Menu.Item>
                  <Menu.Item onClick={() => void print('80mm')}>{t('3-inch thermal')}</Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
            {!cancelled && can(Perm.INVOICES_CANCEL) && (
              <Button
                variant="default"
                color="red"
                leftSection={<IconBan size={16} />}
                onClick={cancel}
              >
                {t('Cancel invoice')}
              </Button>
            )}
          </>
        }
      />

      {cancelled && (
        <Alert color="red" mb="lg" title={t('Cancelled')}>
          {invoice.cancel_reason} · {formatDateTime(invoice.cancelled_at)} ·{' '}
          {invoice.cancelled_by?.full_name || invoice.cancelled_by?.username}
        </Alert>
      )}
      {invoice.print_count > 0 && (
        <Text size="sm" c="dimmed" mb="md">
          {t('Printed {{n}} time(s). Every print after the first is marked "Copy of original".', {
            n: invoice.print_count,
          })}
        </Text>
      )}

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <SectionCard title={t('Particulars')} flush>
            <Table.ScrollContainer minWidth={560}>
              <Table verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th w={50}>{t('S.N.')}</Table.Th>
                    <Table.Th>{t('Particulars')}</Table.Th>
                    <Table.Th ta="right">{t('Qty')}</Table.Th>
                    <Table.Th>{t('Unit')}</Table.Th>
                    <Table.Th ta="right">{t('Rate')}</Table.Th>
                    <Table.Th ta="right">{t('Amount')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {invoice.lines.map((line) => (
                    <Table.Tr key={line.line_no}>
                      <Table.Td c="dimmed">{line.line_no}</Table.Td>
                      <Table.Td>
                        <Text size="sm">{line.description}</Text>
                        {line.details && (
                          <Text size="xs" c="dimmed">
                            {line.details}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {formatQty(line.quantity)}
                      </Table.Td>
                      <Table.Td>{line.unit}</Table.Td>
                      <Table.Td ta="right" className="num">
                        {formatAmount(line.rate)}
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {formatAmount(line.amount)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            <Stack gap={4} p="lg" pt="sm" align="flex-end">
              {(
                [
                  [t('Sub-total'), invoice.subtotal, true],
                  [
                    t('Discount'),
                    `-${invoice.discount_amount}`,
                    toNumber(invoice.discount_amount) > 0,
                  ],
                  [t('Taxable amount'), invoice.taxable_amount, invoice.is_vat_invoice],
                  [
                    t('VAT {{rate}}%', { rate: formatQty(invoice.vat_rate) }),
                    invoice.vat_amount,
                    invoice.is_vat_invoice,
                  ],
                  [t('Round off'), invoice.round_off, toNumber(invoice.round_off) !== 0],
                ] as [string, string, boolean][]
              )
                .filter(([, , show]) => show)
                .map(([label, value]) => (
                  <Group key={String(label)} gap="xl">
                    <Text size="sm" c="dimmed">
                      {label}
                    </Text>
                    <Text size="sm" className="num" miw={110} ta="right">
                      {formatAmount(value as string)}
                    </Text>
                  </Group>
                ))}
              <Group
                gap="xl"
                pt={6}
                style={{ borderTop: '1px solid var(--mantine-color-slate-9)' }}
              >
                <Text fw={600}>{t('Grand total')}</Text>
                <Money
                  value={invoice.total}
                  fw={600}
                  miw={110}
                  ta="right"
                  td={cancelled ? 'line-through' : undefined}
                />
              </Group>
              <Text size="xs" c="dimmed" mt={4}>
                {invoice.amount_in_words}
              </Text>
            </Stack>
          </SectionCard>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="lg">
            {!cancelled && (
              <Card>
                <Text size="sm" c="dimmed" fw={500}>
                  {t('Order balance')}
                </Text>
                <Money
                  value={invoice.order_balance}
                  fz={26}
                  fw={600}
                  c={toNumber(invoice.order_balance) > 0 ? 'red.7' : 'slate.9'}
                  style={{ fontVariantNumeric: 'normal' }}
                />
                <Text size="xs" c="dimmed">
                  {t('Paid')} {formatAmount(invoice.order_paid)}
                </Text>
              </Card>
            )}
            <Card>
              <KeyValue
                labelWidth={100}
                items={[
                  {
                    label: t('Date'),
                    value: <DualDate ad={invoice.invoice_date} bs={invoice.invoice_date_bs} />,
                  },
                  {
                    label: t('Bill to'),
                    value: (
                      <Stack gap={0}>
                        <Anchor component={Link} to={`/customers/${invoice.customer}`} size="sm">
                          {invoice.customer_name}
                        </Anchor>
                        <Text size="xs" c="dimmed">
                          {[invoice.customer_address, invoice.customer_phone]
                            .filter(Boolean)
                            .join(' · ')}
                        </Text>
                      </Stack>
                    ),
                  },
                  { label: t("Buyer's PAN"), value: invoice.customer_pan || '—' },
                  {
                    label: t('Order'),
                    value: (
                      <Anchor component={Link} to={`/orders/${invoice.order.id}`} size="sm">
                        {invoice.order.order_no}
                      </Anchor>
                    ),
                  },
                  {
                    label: t('Issued by'),
                    value: invoice.issued_by.full_name || invoice.issued_by.username,
                  },
                  {
                    label: t('Last printed'),
                    value: formatDateTime(invoice.last_printed_at),
                    hidden: !invoice.last_printed_at,
                  },
                ]}
              />
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  );
}
