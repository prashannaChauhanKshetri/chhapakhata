import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Menu,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import {
  IconBan,
  IconCheck,
  IconDotsVertical,
  IconFileInvoice,
  IconPencil,
  IconPrinter,
  IconReceipt2,
  IconTicket,
  IconTruckDelivery,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { Customer, OrderDetail } from '@/api/types';
import { DualDate } from '@/components/DualDate';
import { KeyValue } from '@/components/KeyValue';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { PageLoader } from '@/components/PageLoader';
import { QueryError } from '@/components/QueryError';
import { openReasonModal } from '@/components/ReasonModal';
import { SectionCard } from '@/components/SectionCard';
import { StageBadge, StatusBadge } from '@/components/StatusBadge';
import { notifyError, notifySuccess } from '@/lib/forms';
import { deadlineLabel, formatAmount, formatDateTime, formatQty, toNumber } from '@/lib/format';
import { INVOICE_STATUS, ORDER_STATUS, PAYMENT_STATUS } from '@/lib/status';

import { openReceivePayment } from '../billing/ReceivePaymentForm';
import { openDeliver } from './DeliverForm';

export default function OrderDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const orderId = Number(id);
  const navigate = useNavigate();
  const client = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const {
    data: order,
    error,
    refetch,
  } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => apiGet<OrderDetail>(`/api/v1/orders/${orderId}/`),
  });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;
  if (!order) return <PageLoader />;
  const a = order.actions;

  const refresh = async () => {
    await Promise.all(
      ['order', 'orders', 'board', 'jobs', 'dashboard', 'invoices'].map((k) =>
        client.invalidateQueries({ queryKey: [k] }),
      ),
    );
  };

  const run = async (key: string, fn: () => Promise<unknown>, success: string) => {
    setBusy(key);
    try {
      await fn();
      await refresh();
      notifySuccess(success);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(null);
    }
  };

  const confirm = () =>
    modals.openConfirmModal({
      title: t('Confirm {{no}}?', { no: order.order_no }),
      children: <Text size="sm">{t('This opens one production job per item on the board.')}</Text>,
      labels: { confirm: t('Confirm order'), cancel: t('Not yet') },
      onConfirm: () =>
        void run(
          'confirm',
          () =>
            unwrap(
              api.POST('/api/v1/orders/{id}/confirm/', { params: { path: { id: order.id } } }),
            ),
          t('Order confirmed'),
        ),
    });

  const issueInvoice = () =>
    modals.openConfirmModal({
      title: t('Issue invoice for {{no}}?', { no: order.order_no }),
      children: (
        <Text size="sm">
          {t(
            'An invoice cannot be deleted. After this, the order cannot be edited unless the owner cancels the invoice.',
          )}
        </Text>
      ),
      labels: { confirm: t('Issue invoice'), cancel: t('Cancel') },
      onConfirm: () =>
        void run(
          'invoice',
          () =>
            unwrap(
              api.POST('/api/v1/orders/{id}/invoice/', {
                params: { path: { id: order.id } },
                body: { notes: '' },
              }),
            ),
          t('Invoice issued'),
        ),
    });

  const cancel = () =>
    openReasonModal({
      title: t('Cancel {{no}}', { no: order.order_no }),
      message:
        toNumber(order.paid_amount) > 0
          ? t(
              "Its jobs leave the board. The {{amount}} already paid stays as the customer's advance.",
              { amount: formatAmount(order.paid_amount) },
            )
          : t('Its jobs leave the board. This cannot be undone.'),
      confirmLabel: t('Cancel order'),
      onConfirm: async (reason) => {
        await unwrap(
          api.POST('/api/v1/orders/{id}/cancel/', {
            params: { path: { id: order.id } },
            body: { reason },
          }),
        );
        await refresh();
        notifySuccess(t('Order cancelled'));
      },
    });

  const receive = async () => {
    const customer = await apiGet<Customer>(`/api/v1/customers/${order.customer.id}/`);
    openReceivePayment({ customer, orderId: order.id, suggestedAmount: order.balance_due });
  };

  const printQuotation = () =>
    openFile(`/api/v1/orders/${order.id}/quotation-pdf/`).catch((e) => notifyError(e));
  const printTickets = () =>
    openFile(`/api/v1/orders/${order.id}/job-tickets-pdf/`).catch((e) => notifyError(e));
  const activeInvoice = order.invoices.find((i) => i.status === 'issued');

  return (
    <>
      <PageHeader
        back={{ to: '/orders', label: t('Orders') }}
        title={order.order_no}
        badge={
          <Group gap={6}>
            <StatusBadge value={order.status} map={ORDER_STATUS} />
            {order.is_urgent && <Badge color="red">{t('Urgent')}</Badge>}
            {order.source === 'import' && (
              <Badge color="slate" variant="outline">
                {t('Imported')}
              </Badge>
            )}
          </Group>
        }
        description={`${order.customer.name}${order.customer.phone ? ` · ${order.customer.phone}` : ''}`}
        actions={
          <>
            {a.can_confirm && (
              <Button
                leftSection={<IconCheck size={16} />}
                loading={busy === 'confirm'}
                onClick={confirm}
              >
                {t('Confirm order')}
              </Button>
            )}
            {a.can_deliver && (
              <Button
                leftSection={<IconTruckDelivery size={16} />}
                onClick={() => openDeliver(order)}
              >
                {t('Deliver')}
              </Button>
            )}
            {a.can_receive_payment && (
              <Button
                variant="default"
                leftSection={<IconReceipt2 size={16} />}
                onClick={() => void receive()}
              >
                {t('Receive payment')}
              </Button>
            )}
            {a.can_invoice && !a.can_deliver && (
              <Button
                variant="default"
                leftSection={<IconFileInvoice size={16} />}
                loading={busy === 'invoice'}
                onClick={issueInvoice}
              >
                {t('Issue invoice')}
              </Button>
            )}
            <Menu position="bottom-end" width={220}>
              <Menu.Target>
                <Button variant="default" px="xs" aria-label={t('More actions')}>
                  <IconDotsVertical size={16} />
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconPrinter size={16} />}
                  onClick={() => void printQuotation()}
                >
                  {order.status === 'quotation' ? t('Print quotation') : t('Print estimate')}
                </Menu.Item>
                {order.status !== 'quotation' && (
                  <Menu.Item
                    leftSection={<IconTicket size={16} />}
                    onClick={() => void printTickets()}
                  >
                    {t('Print job tickets')}
                  </Menu.Item>
                )}
                {activeInvoice && (
                  <Menu.Item
                    leftSection={<IconFileInvoice size={16} />}
                    component={Link}
                    to={`/invoices/${activeInvoice.id}`}
                  >
                    {t('Open invoice')}
                  </Menu.Item>
                )}
                {a.can_edit && (
                  <Menu.Item
                    leftSection={<IconPencil size={16} />}
                    onClick={() => navigate(`/orders/${order.id}/edit`)}
                  >
                    {t('Edit order')}
                  </Menu.Item>
                )}
                {a.can_cancel && (
                  <>
                    <Menu.Divider />
                    <Menu.Item color="red" leftSection={<IconBan size={16} />} onClick={cancel}>
                      {t('Cancel order')}
                    </Menu.Item>
                  </>
                )}
              </Menu.Dropdown>
            </Menu>
          </>
        }
      />

      {order.status === 'cancelled' && (
        <Alert color="red" mb="lg" title={t('Cancelled')}>
          {order.cancel_reason} · {formatDateTime(order.cancelled_at)}
        </Alert>
      )}

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack gap="lg">
            <SectionCard title={t('Items')} flush>
              <Table.ScrollContainer minWidth={640}>
                <Table verticalSpacing="sm" highlightOnHover={false}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th w={40}>#</Table.Th>
                      <Table.Th>{t('Item')}</Table.Th>
                      <Table.Th>{t('Size')}</Table.Th>
                      <Table.Th ta="right">{t('Sq ft')}</Table.Th>
                      <Table.Th ta="right">{t('Rate')}</Table.Th>
                      <Table.Th ta="right">{t('Amount')}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {order.items.map((item) => (
                      <Table.Tr key={item.id}>
                        <Table.Td c="dimmed">{item.line_no}</Table.Td>
                        <Table.Td>
                          <Text size="sm" fw={500}>
                            {item.media_name}
                            {item.description ? ` · ${item.description}` : ''}
                          </Text>
                          {item.addons.length > 0 && (
                            <Text size="xs" c="dimmed">
                              +{' '}
                              {item.addons
                                .map((ad) => `${ad.name} (${formatAmount(ad.amount)})`)
                                .join(', ')}
                            </Text>
                          )}
                          {item.finishing && (
                            <Text size="xs" c="dimmed">
                              {t('Finishing')}: {item.finishing}
                            </Text>
                          )}
                          {item.job && (
                            <Group gap={6} mt={4}>
                              <Text size="xs" c="dimmed">
                                {item.job.job_no}
                              </Text>
                              <StageBadge stage={item.job.stage} />
                            </Group>
                          )}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {item.size_label
                              ? `${item.size_label} × ${item.quantity}`
                              : t('{{n}} pcs', { n: item.quantity })}
                          </Text>
                          {item.min_applied && (
                            <Text size="xs" c="amber.8">
                              {t('Min. {{min}} sq ft each', { min: formatQty(item.min_sqft) })}
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td ta="right" className="num">
                          {item.pricing_unit === 'piece'
                            ? '—'
                            : formatQty(item.total_billable_sqft)}
                        </Table.Td>
                        <Table.Td ta="right" className="num">
                          {formatAmount(item.rate)}
                          {item.pricing_unit === 'piece' && (
                            <Text size="xs" c="dimmed">
                              {t('per piece')}
                            </Text>
                          )}
                          {order.source !== 'import' && item.rate_source !== 'card' && (
                            <Text size="xs" c="dimmed">
                              {item.rate_source === 'previous' ? t('last rate') : t('custom')}
                              {item.card_rate ? ` · ${t('card')} ${formatQty(item.card_rate)}` : ''}
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td ta="right" className="num" fw={500}>
                          {formatAmount(item.line_total)}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
              <Stack gap={4} p="lg" pt="sm" align="flex-end">
                {(
                  [
                    [t('Sub-total'), order.subtotal, true],
                    [
                      t('Discount'),
                      `-${order.discount_amount}`,
                      toNumber(order.discount_amount) > 0,
                    ],
                    [
                      t('VAT {{rate}}%', { rate: formatQty(order.vat_rate) }),
                      order.vat_amount,
                      toNumber(order.vat_amount) > 0,
                    ],
                    [t('Round off'), order.round_off, toNumber(order.round_off) !== 0],
                  ] as [string, string, boolean][]
                )
                  .filter(([, , show]) => show)
                  .map(([label, value]) => (
                    <Group key={String(label)} gap="xl" justify="flex-end">
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
                  justify="flex-end"
                  pt={6}
                  style={{ borderTop: '1px solid var(--mantine-color-slate-9)' }}
                >
                  <Text fw={600}>{t('Total')}</Text>
                  <Money value={order.total} fw={600} miw={110} ta="right" />
                </Group>
              </Stack>
            </SectionCard>

            {order.notes && (
              <SectionCard title={t('Notes')}>
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                  {order.notes}
                </Text>
              </SectionCard>
            )}
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="lg">
            <Card>
              <Text size="sm" c="dimmed" fw={500}>
                {t('Balance due')}
              </Text>
              <Money
                value={order.balance_due}
                fz={28}
                fw={600}
                c={toNumber(order.balance_due) > 0 ? 'red.7' : 'slate.9'}
                style={{ fontVariantNumeric: 'normal' }}
              />
              <Group gap="lg" mt="xs">
                <div>
                  <Text size="xs" c="dimmed">
                    {t('Total')}
                  </Text>
                  <Money value={order.total} size="sm" />
                </div>
                <div>
                  <Text size="xs" c="dimmed">
                    {t('Paid')}
                  </Text>
                  <Money value={order.paid_amount} size="sm" />
                </div>
              </Group>
            </Card>
            <Card>
              <KeyValue
                labelWidth={100}
                items={[
                  {
                    label: t('Customer'),
                    value: (
                      <Anchor component={Link} to={`/customers/${order.customer.id}`} size="sm">
                        {order.customer.name}
                      </Anchor>
                    ),
                  },
                  {
                    label: t('Order date'),
                    value: <DualDate ad={order.order_date} bs={order.order_date_bs} />,
                  },
                  {
                    label: t('Deliver by'),
                    value: order.deadline ? (
                      <Stack gap={0}>
                        <Text size="sm">{formatDateTime(order.deadline)}</Text>
                        {['confirmed', 'in_production'].includes(order.status) && (
                          <Text size="xs" c="dimmed">
                            {deadlineLabel(order.deadline)}
                          </Text>
                        )}
                      </Stack>
                    ) : (
                      '—'
                    ),
                  },
                  {
                    label: t('Taken by'),
                    value: order.created_by.full_name || order.created_by.username,
                  },
                  {
                    label: t('Delivered'),
                    value: formatDateTime(order.delivered_at),
                    hidden: !order.delivered_at,
                  },
                ]}
              />
            </Card>
            <SectionCard title={t('Invoices')}>
              {order.invoices.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t('No invoice yet.')}
                </Text>
              ) : (
                <Stack gap="xs">
                  {order.invoices.map((inv) => (
                    <Group key={inv.id} justify="space-between" wrap="nowrap">
                      <div>
                        <Anchor component={Link} to={`/invoices/${inv.id}`} size="sm" fw={500}>
                          {inv.invoice_no}
                        </Anchor>
                        <Text size="xs" c="dimmed">
                          {inv.invoice_date_bs} BS
                        </Text>
                      </div>
                      <StatusBadge value={inv.status} map={INVOICE_STATUS} />
                    </Group>
                  ))}
                </Stack>
              )}
            </SectionCard>
            <SectionCard title={t('Payments')}>
              {order.payments.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t('No payment yet.')}
                </Text>
              ) : (
                <Stack gap="xs">
                  {order.payments.map((p) => (
                    <Group key={p.id} justify="space-between" wrap="nowrap">
                      <div>
                        <Text
                          size="sm"
                          fw={500}
                          td={p.status === 'void' ? 'line-through' : undefined}
                        >
                          {p.receipt_no} · {p.mode_label}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {p.payment_date}
                          {p.is_advance ? ` · ${t('advance')}` : ''}
                        </Text>
                      </div>
                      <Group gap={6} wrap="nowrap">
                        {p.status === 'void' && (
                          <StatusBadge value={p.status} map={PAYMENT_STATUS} size="sm" />
                        )}
                        <Money value={p.amount} size="sm" />
                      </Group>
                    </Group>
                  ))}
                </Stack>
              )}
            </SectionCard>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  );
}
