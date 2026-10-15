import {
  ActionIcon,
  Anchor,
  Button,
  Card,
  Group,
  Menu,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import {
  IconBan,
  IconDotsVertical,
  IconPrinter,
  IconReceipt2,
  IconSearch,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { DataTable } from 'mantine-datatable';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { Paginated, Payment } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { DualDate } from '@/components/DualDate';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { openReasonModal } from '@/components/ReasonModal';
import { StatusBadge } from '@/components/StatusBadge';
import { notifyError, notifySuccess } from '@/lib/forms';
import { Perm } from '@/lib/permissions';
import { PAYMENT_MODES, PAYMENT_STATUS } from '@/lib/status';
import { PAGE_SIZE, useListState } from '@/lib/useListState';

import { openReceivePayment } from './ReceivePaymentForm';

export default function PaymentsPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const list = useListState(['mode', 'date_from', 'date_to'] as const, '-payment_date');
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ['payments', list.query],
    queryFn: () => apiGet<Paginated<Payment>>('/api/v1/payments/', list.query),
    placeholderData: (previous) => previous,
  });

  // Dashboard shortcut: /payments?receive=1 opens the form straight away.
  useEffect(() => {
    if (params.get('receive') === '1' && can(Perm.PAYMENTS_RECEIVE)) {
      openReceivePayment({});
      const next = new URLSearchParams(params);
      next.delete('receive');
      setParams(next, { replace: true });
    }
  }, [params, setParams, can]);

  const voidPayment = (p: Payment) =>
    openReasonModal({
      title: t('Void receipt {{no}}', { no: p.receipt_no }),
      message: t(
        "Use this for a mistaken entry or a bounced cheque. The amount is added back to the customer's dues.",
      ),
      confirmLabel: t('Void payment'),
      onConfirm: async (reason) => {
        await unwrap(
          api.POST('/api/v1/payments/{id}/void/', {
            params: { path: { id: p.id } },
            body: { reason },
          }),
        );
        await Promise.all(
          ['payments', 'order', 'customer', 'customers', 'dashboard'].map((k) =>
            client.invalidateQueries({ queryKey: [k] }),
          ),
        );
        notifySuccess(t('Payment voided'));
      },
    });

  const range: [string | null, string | null] = [
    list.filters.date_from || null,
    list.filters.date_to || null,
  ];

  return (
    <>
      <PageHeader
        title={t('Payments')}
        description={t('Advances, settlements and payments towards dues.')}
        actions={
          can(Perm.PAYMENTS_RECEIVE) && (
            <Button leftSection={<IconReceipt2 size={16} />} onClick={() => openReceivePayment({})}>
              {t('Receive payment')}
            </Button>
          )
        }
      />
      <Card padding={0}>
        <Group p="md" gap="sm" wrap="wrap">
          <TextInput
            placeholder={t('Receipt no., customer, reference or cheque')}
            leftSection={<IconSearch size={16} />}
            value={list.search}
            onChange={(e) => list.setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 240px' }}
            aria-label={t('Search payments')}
          />
          <Select
            placeholder={t('All modes')}
            clearable
            w={170}
            data={PAYMENT_MODES}
            value={list.filters.mode || null}
            onChange={(v) => list.setFilter('mode', v)}
            aria-label={t('Payment mode')}
          />
          <DatePickerInput
            type="range"
            placeholder={t('Any date')}
            clearable
            w={260}
            valueFormat="D MMM YYYY"
            value={range}
            maxDate={dayjs().format('YYYY-MM-DD')}
            onChange={(v) => {
              const [from, to] = v as [string | null, string | null];
              if ((from && to) || (!from && !to)) {
                list.setFilter('date_from', from);
                list.setFilter('date_to', to);
              }
            }}
            aria-label={t('Date range')}
          />
        </Group>
        {error ? (
          <Stack p="md">
            <QueryError error={error} onRetry={() => void refetch()} />
          </Stack>
        ) : (
          <DataTable<Payment>
            minHeight={260}
            highlightOnHover
            records={data?.results ?? []}
            fetching={isFetching && !data}
            totalRecords={data?.count ?? 0}
            recordsPerPage={PAGE_SIZE}
            page={list.page}
            onPageChange={list.setPage}
            sortStatus={list.sortStatus as never}
            onSortStatusChange={list.setSort as never}
            noRecordsText={t('No payments here')}
            columns={[
              {
                accessor: 'receipt_no',
                title: t('Receipt'),
                render: (p) => (
                  <div>
                    <Text size="sm" fw={500} td={p.status === 'void' ? 'line-through' : undefined}>
                      {p.receipt_no}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {p.received_by.full_name || p.received_by.username}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'payment_date',
                title: t('Date'),
                sortable: true,
                render: (p) => <DualDate ad={p.payment_date} bs={p.payment_date_bs} />,
              },
              {
                accessor: 'customer',
                title: t('Customer'),
                render: (p) => (
                  <div>
                    <Anchor component={Link} to={`/customers/${p.customer.id}`} size="sm">
                      {p.customer.name}
                    </Anchor>
                    <Text size="xs" c="dimmed">
                      {p.order ? (
                        <>
                          {p.order.order_no}
                          {p.is_advance ? ` · ${t('advance')}` : ''}
                        </>
                      ) : (
                        t('On account')
                      )}
                    </Text>
                  </div>
                ),
              },
              {
                accessor: 'mode',
                title: t('Mode'),
                render: (p) => (
                  <div>
                    <Text size="sm">{p.mode_label}</Text>
                    {(p.reference_no || p.cheque_no) && (
                      <Text size="xs" c="dimmed">
                        {p.cheque_no ? `${t('Cheque')} ${p.cheque_no}` : p.reference_no}
                      </Text>
                    )}
                  </div>
                ),
              },
              {
                accessor: 'status',
                title: t('Status'),
                visibleMediaQuery: '(min-width: 62em)',
                render: (p) => <StatusBadge value={p.status} map={PAYMENT_STATUS} />,
              },
              {
                accessor: 'amount',
                title: t('Amount'),
                sortable: true,
                textAlign: 'right',
                render: (p) => <Money value={p.amount} prefix={false} size="sm" />,
              },
              {
                accessor: 'actions',
                title: '',
                width: 48,
                render: (p) => (
                  <Menu position="bottom-end" withinPortal>
                    <Menu.Target>
                      <ActionIcon aria-label={t('Payment actions')}>
                        <IconDotsVertical size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconPrinter size={16} />}
                        onClick={() =>
                          void openFile(`/api/v1/payments/${p.id}/receipt/?size=80mm`).catch((e) =>
                            notifyError(e),
                          )
                        }
                      >
                        {t('3-inch receipt')}
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconPrinter size={16} />}
                        onClick={() =>
                          void openFile(`/api/v1/payments/${p.id}/receipt/?size=a5`).catch((e) =>
                            notifyError(e),
                          )
                        }
                      >
                        {t('A5 receipt')}
                      </Menu.Item>
                      {can(Perm.PAYMENTS_VOID) && p.status === 'valid' && (
                        <Menu.Item
                          color="red"
                          leftSection={<IconBan size={16} />}
                          onClick={() => voidPayment(p)}
                        >
                          {t('Void payment')}
                        </Menu.Item>
                      )}
                    </Menu.Dropdown>
                  </Menu>
                ),
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
