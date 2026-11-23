import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  Menu,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core';
import {
  IconCalendarMonth,
  IconCash,
  IconChevronLeft,
  IconChevronRight,
  IconDots,
  IconPrinter,
  IconArrowBackUp,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { api, unwrap } from '@/api/client';
import { openFile } from '@/api/files';
import { apiGet } from '@/api/http';
import type { MonthSheet, Payroll } from '@/api/types';
import { DataTable } from '@/components/DataTable';
import { Money } from '@/components/Money';
import { QueryError } from '@/components/QueryError';
import { openReasonModal } from '@/components/ReasonModal';
import { StatCard } from '@/components/StatCard';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatNPR, toNumber } from '@/lib/format';

import { openAttendanceCalendar } from './AttendanceCalendar';
import { openAdvanceForm, openPaySalary } from './StaffForms';

const monthParam = (year: number, month: number) => `${year}-${String(month).padStart(2, '0')}`;

/** What makes up one worker's pay for the month, line by line, as on the slip. */
function Breakdown({
  sheet,
  month,
  onChanged,
}: {
  sheet: MonthSheet;
  month: string;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const paid = !!sheet.payment;
  const removeAdvance = async (id: number) => {
    try {
      await unwrap(api.DELETE('/api/v1/staff-advances/{id}/', { params: { path: { id } } }));
      notifySuccess(t('Advance removed'));
      onChanged();
    } catch (e) {
      notifyError(e, t('Could not remove the advance'));
    }
  };
  const line = (label: React.ReactNode, amount: React.ReactNode, detail?: React.ReactNode) => (
    <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
      <div style={{ minWidth: 0 }}>
        <Text size="sm">{label}</Text>
        {detail && (
          <Text size="xs" c="dimmed">
            {detail}
          </Text>
        )}
      </div>
      <Text size="sm" className="num" style={{ whiteSpace: 'nowrap' }}>
        {amount}
      </Text>
    </Group>
  );
  return (
    <Stack gap={8} px="var(--ck-card-pad)" py="sm" bg="slate.0">
      {line(
        t('Salary ({{n}} of {{days}} days)', { n: sheet.days_employed, days: sheet.days_in_month }),
        formatAmount(sheet.base_pay),
        t('One day = {{rate}}', { rate: formatNPR(sheet.day_rate) }),
      )}
      {sheet.absent_dates.length > 0 &&
        line(
          t('Days absent: {{n}}', { n: sheet.absent_dates.length }),
          `− ${formatAmount(sheet.absent_deduction)}`,
          sheet.absent_dates.map((d) => d.bs).join(', '),
        )}
      {sheet.worked_dates.length > 0 &&
        line(
          t('Saturdays worked: {{n}}', { n: sheet.worked_dates.length }),
          `+ ${formatAmount(sheet.holiday_pay)}`,
          `${sheet.worked_dates.map((d) => d.bs).join(', ')} · ${t('{{rate}} each', { rate: formatNPR(sheet.holiday_rate) })}`,
        )}
      {toNumber(sheet.opening_balance) !== 0 &&
        line(
          t('Balance up to {{month}}', { month: sheet.opening_label }),
          toNumber(sheet.opening_balance) > 0
            ? `+ ${formatAmount(sheet.opening_balance)}`
            : `− ${formatAmount(Math.abs(toNumber(sheet.opening_balance)))}`,
          toNumber(sheet.opening_balance) > 0
            ? t('Owed to the worker from before')
            : t('Owed by the worker from before (old advance)'),
        )}
      {sheet.advances.map((a) => (
        <Group key={a.id} justify="space-between" wrap="nowrap" gap="md">
          <div style={{ minWidth: 0 }}>
            <Text size="sm">{t('Advance on {{date}}', { date: a.date_bs })}</Text>
            {a.note && (
              <Text size="xs" c="dimmed">
                {a.note}
              </Text>
            )}
          </div>
          <Group gap={4} wrap="nowrap">
            <Text size="sm" className="num">
              − {formatAmount(a.amount)}
            </Text>
            {!paid && !a.carried && (
              <Tooltip label={t('Remove this advance')}>
                <ActionIcon
                  size="sm"
                  color="red"
                  onClick={() => void removeAdvance(a.id)}
                  aria-label={t('Remove this advance')}
                >
                  <IconTrash size={14} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        </Group>
      ))}
      <Group
        justify="space-between"
        pt={6}
        style={{ borderTop: '1px solid var(--mantine-color-slate-3)' }}
      >
        <Text fw={600}>{paid ? t('Paid') : t('To pay')}</Text>
        <Money value={sheet.net} fw={600} />
      </Group>
      {sheet.payment && (
        <Text size="xs" c="dimmed">
          {t('Paid on {{date}} BS · {{mode}} · by {{who}}', {
            date: sheet.payment.paid_on_bs,
            mode: sheet.payment.mode_label,
            who: sheet.payment.paid_by_name,
          })}
        </Text>
      )}
      {!paid && sheet.days_ahead > 0 && (
        <Text size="xs" c="dimmed">
          {t('{{n}} days still to come count as present.', { n: sheet.days_ahead })}
        </Text>
      )}
      {sheet.notes.map((note) => (
        <Text key={note} size="xs" c="blue.8">
          {note}
        </Text>
      ))}
      <Button
        variant="default"
        size="xs"
        w="fit-content"
        leftSection={<IconCalendarMonth size={14} />}
        onClick={() => openAttendanceCalendar(sheet.staff, month)}
      >
        {t('Days of {{name}}', { name: sheet.staff.name })}
      </Button>
    </Stack>
  );
}

export function SalaryTab() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [month, setMonth] = useState<string | null>(null); // null: this month
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: ['staff', 'salary', month],
    queryFn: () => apiGet<Payroll>('/api/v1/salary/', month ? { month } : undefined),
  });
  const refresh = () => void client.invalidateQueries({ queryKey: ['staff'] });

  const undo = (sheet: MonthSheet) =>
    openReasonModal({
      title: t('Undo salary payment'),
      message: t(
        'The payment of {{amount}} to {{name}} is removed and the month opens again for changes.',
        { amount: formatNPR(sheet.net), name: sheet.staff.name },
      ),
      confirmLabel: t('Undo payment'),
      onConfirm: async (reason) => {
        await unwrap(
          api.POST('/api/v1/salary-payments/{id}/undo/', {
            params: { path: { id: sheet.payment!.id } },
            body: { reason },
          }),
        );
        refresh();
        notifySuccess(t('Payment undone'));
      },
    });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;

  const rows = data?.rows ?? [];
  const unpaid = rows.filter((r) => !r.payment);
  return (
    <Stack gap="md">
      <Card>
        <Group justify="space-between" wrap="nowrap">
          <Tooltip label={data?.previous.label}>
            <ActionIcon
              variant="default"
              size={36}
              disabled={!data}
              onClick={() => data && setMonth(monthParam(data.previous.year, data.previous.month))}
              aria-label={t('Previous month')}
            >
              <IconChevronLeft size={18} />
            </ActionIcon>
          </Tooltip>
          <div style={{ textAlign: 'center' }}>
            <Text fw={600} size="lg">
              {data?.label ?? '…'}
            </Text>
            <Text size="xs" c="dimmed">
              {t('Salary month (BS)')}
            </Text>
          </div>
          <Tooltip label={data?.next?.label ?? t('Not started yet')}>
            <ActionIcon
              variant="default"
              size={36}
              disabled={!data?.next}
              onClick={() => data?.next && setMonth(monthParam(data.next.year, data.next.month))}
              aria-label={t('Next month')}
            >
              <IconChevronRight size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Card>

      <SimpleGrid cols={{ base: 2 }} spacing="sm">
        <StatCard
          label={t('To pay')}
          value={formatNPR(toNumber(data?.total_net) - toNumber(data?.total_paid))}
          hint={t('{{n}} not paid yet', { n: unpaid.length })}
          loading={!data}
        />
        <StatCard
          label={t('Paid')}
          value={formatNPR(data?.total_paid)}
          hint={t('{{n}} paid', { n: rows.length - unpaid.length })}
          loading={!data}
        />
      </SimpleGrid>

      <Card padding={0}>
        <DataTable<MonthSheet>
          minHeight={160}
          records={rows}
          fetching={isFetching && !data}
          idAccessor={(r) => r.staff.id}
          phoneAside="net"
          noRecordsText={t('No staff worked in this month')}
          rowExpansion={{
            content: ({ record }) => (
              <Breakdown
                sheet={record}
                month={monthParam(data!.year, data!.month)}
                onChanged={refresh}
              />
            ),
          }}
          columns={[
            {
              accessor: 'staff',
              title: t('Staff'),
              render: (r) => (
                <div>
                  <Text size="sm" fw={500}>
                    {r.staff.name}
                  </Text>
                  {r.staff.job_title && (
                    <Text size="xs" c="dimmed">
                      {r.staff.job_title}
                    </Text>
                  )}
                </div>
              ),
            },
            {
              accessor: 'status',
              title: t('Status'),
              render: (r) =>
                r.payment ? (
                  <Badge color="green">{t('Paid')}</Badge>
                ) : (
                  <Badge color="amber">{t('Not paid')}</Badge>
                ),
            },
            {
              accessor: 'monthly_salary',
              title: t('Salary'),
              textAlign: 'right',
              render: (r) => <Money value={r.monthly_salary} prefix={false} size="sm" />,
            },
            {
              accessor: 'absent',
              title: t('Absent'),
              textAlign: 'right',
              render: (r) => (r.absent_dates.length ? r.absent_dates.length : '—'),
            },
            {
              accessor: 'worked',
              title: t('Saturdays'),
              textAlign: 'right',
              render: (r) => (r.worked_dates.length ? r.worked_dates.length : '—'),
            },
            {
              accessor: 'advances_total',
              title: t('Advances'),
              textAlign: 'right',
              render: (r) =>
                toNumber(r.advances_total) ? (
                  <Money value={r.advances_total} prefix={false} size="sm" />
                ) : (
                  '—'
                ),
            },
            {
              accessor: 'net',
              title: t('Net pay'),
              textAlign: 'right',
              render: (r) => <Money value={r.net} prefix={false} size="sm" fw={600} />,
            },
            {
              accessor: 'actions',
              title: '',
              textAlign: 'right',
              render: (r) => (
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon
                      onClick={(e) => e.stopPropagation()}
                      aria-label={t('Actions for {{name}}', { name: r.staff.name })}
                    >
                      <IconDots size={18} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
                    {!r.payment && r.days_employed > 0 && data && (
                      <Menu.Item
                        leftSection={<IconCash size={16} />}
                        onClick={() => openPaySalary(r, data.year, data.month, data.label)}
                      >
                        {t('Pay salary')}
                      </Menu.Item>
                    )}
                    <Menu.Item
                      leftSection={<IconCalendarMonth size={16} />}
                      onClick={() =>
                        data && openAttendanceCalendar(r.staff, monthParam(data.year, data.month))
                      }
                    >
                      {t('Attendance days')}
                    </Menu.Item>
                    {!r.payment && (
                      <Menu.Item
                        leftSection={<IconPlus size={16} />}
                        onClick={() => openAdvanceForm(r.staff)}
                      >
                        {t('Give advance')}
                      </Menu.Item>
                    )}
                    {r.payment && (
                      <>
                        <Menu.Item
                          leftSection={<IconPrinter size={16} />}
                          onClick={() =>
                            void openFile(`/api/v1/salary-payments/${r.payment!.id}/slip/`).catch(
                              (e) => notifyError(e, t('Could not open the salary slip')),
                            )
                          }
                        >
                          {t('Salary slip')}
                        </Menu.Item>
                        <Menu.Item
                          color="red"
                          leftSection={<IconArrowBackUp size={16} />}
                          onClick={() => undo(r)}
                        >
                          {t('Undo payment')}
                        </Menu.Item>
                      </>
                    )}
                  </Menu.Dropdown>
                </Menu>
              ),
            },
          ]}
        />
      </Card>
      {data && rows.length === 0 && (
        <Button component={Link} to="/staff/list" variant="default" w="fit-content">
          {t('Add staff')}
        </Button>
      )}
      <Text size="xs" c="dimmed">
        {t(
          'Tap a name to see the days and advances. One day’s pay is the monthly salary ÷ the days in that Nepali month.',
        )}
      </Text>
    </Stack>
  );
}
