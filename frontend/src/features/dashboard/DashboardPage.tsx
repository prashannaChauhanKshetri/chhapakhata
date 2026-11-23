import { Alert, Anchor, Button, Grid, Group, Stack, Text } from '@mantine/core';
import { IconDatabaseExclamation, IconReceipt2 } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { apiGet } from '@/api/http';
import type { Dashboard, DateConversion } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { DataTable } from '@/components/DataTable';
import { EmptyState } from '@/components/EmptyState';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { SectionCard } from '@/components/SectionCard';
import { ReportSkeleton } from '@/components/Skeletons';
import { StageBadge } from '@/components/StatusBadge';
import { deadlineLabel, formatDate, formatNPRCompact, formatQty } from '@/lib/format';
import { Perm } from '@/lib/permissions';

import { AttendanceRegister } from '../staff/AttendanceRegister';
import classes from './Dashboard.module.css';
import { SalesTrendCard } from './SalesTrendCard';

/** Columns shown only where there is room; on a phone they fold into the first. */
const WIDE = '(min-width: 48em)';

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

/** One figure in the "today" strip; a link when there is a page behind it. */
function Figure({
  label,
  value,
  sub,
  to,
  color,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  to?: string;
  color?: string;
}) {
  const body = (
    <>
      <div className={classes.label}>{label}</div>
      <div className={classes.value} style={color ? { color } : undefined}>
        {value}
      </div>
      {sub && <div className={classes.sub}>{sub}</div>}
    </>
  );
  return to ? (
    <Link to={to} className={classes.figure}>
      {body}
    </Link>
  ) : (
    <div className={classes.figure}>{body}</div>
  );
}

function SeeAll({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Anchor component={Link} to={to} size="sm">
      {children}
    </Anchor>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const { data, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiGet<Dashboard>('/api/v1/dashboard/'),
    refetchInterval: 60_000,
    placeholderData: (previous) => previous,
  });
  const { data: today } = useQuery({
    queryKey: ['utils', 'today'],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/'),
    staleTime: 10 * 60_000,
  });

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;

  const jobs = data?.jobs;
  const late = (deadline: string | null) => deadline !== null && new Date(deadline) < new Date();
  const weekday = data ? WEEKDAYS[new Date(`${data.date}T00:00:00`).getDay()] : '';

  const readyCard = data?.ready_orders && (
    <SectionCard title={t('Ready for collection')} flush>
      {data.ready_orders.length === 0 ? (
        <EmptyState compact title={t('No orders waiting')} />
      ) : (
        <DataTable
          records={data.ready_orders}
          noHeader
          verticalSpacing={8}
          highlightOnHover
          onRowClick={({ record }) => void navigate(`/orders/${record.id}`)}
          columns={[
            {
              accessor: 'order_no',
              render: (o) => (
                <div>
                  <Text size="sm" fw={500}>
                    {o.order_no}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {o.customer} · {o.phone}
                  </Text>
                </div>
              ),
            },
            {
              accessor: 'total',
              textAlign: 'right',
              render: (o) => <Money value={o.total} size="sm" />,
            },
          ]}
        />
      )}
    </SectionCard>
  );

  return (
    <>
      <PageHeader
        title={today?.bs_long ?? t('Today')}
        description={data ? `${t(weekday)} · ${formatDate(data.date)}` : undefined}
        actions={
          can(Perm.PAYMENTS_RECEIVE) && (
            <Button
              component={Link}
              to="/payments?receive=1"
              variant="default"
              leftSection={<IconReceipt2 size={16} />}
            >
              {t('Receive payment')}
            </Button>
          )
        }
      />

      <Stack gap="md">
        {data?.backup?.is_stale && (
          <Alert color="amber" icon={<IconDatabaseExclamation size={18} />} p="sm">
            <Group justify="space-between" gap="sm">
              <Text size="sm">
                <strong>{t('Backup needs attention.')}</strong>{' '}
                {data.backup.last_success_at
                  ? t('The last good backup was on {{date}}.', {
                      date: formatDate(data.backup.last_success_at),
                    })
                  : t('No backup has been taken yet.')}
              </Text>
              <Button component={Link} to="/settings/backups" size="xs" variant="default">
                {t('Open backups')}
              </Button>
            </Group>
          </Alert>
        )}

        {/* -- Today in figures ------------------------------------------------------ */}
        {data && (
          <div className={classes.today}>
            {data.today && (
              <>
                <Figure
                  label={t('Sales today')}
                  value={formatNPRCompact(data.today.sales)}
                  sub={t('{{count}} invoices', { count: data.today.invoices })}
                  to={can(Perm.INVOICES_VIEW) ? '/invoices' : undefined}
                />
                <Figure
                  label={t('Collected today')}
                  value={formatNPRCompact(data.today.collections)}
                  sub={t('{{count}} payments', { count: data.today.payments })}
                  to={can(Perm.PAYMENTS_VIEW) ? '/payments' : undefined}
                />
              </>
            )}
            {data.dues && (
              <Figure
                label={t('Dues to collect')}
                value={formatNPRCompact(data.dues.total)}
                color={
                  Number(data.dues.over_90_days) > 0 ? 'var(--mantine-color-red-7)' : undefined
                }
                sub={t('{{count}} customers · {{amount}} over 90 days', {
                  count: data.dues.customers,
                  amount: formatNPRCompact(data.dues.over_90_days),
                })}
                to="/reports/pending-dues"
              />
            )}
            {jobs && (
              <Figure
                label={t('Jobs due today')}
                value={jobs.due_today}
                sub={
                  <>
                    {jobs.overdue > 0 && (
                      <Text span size="xs" c="red.7" fw={600}>
                        {t('{{count}} overdue', { count: jobs.overdue })} ·{' '}
                      </Text>
                    )}
                    {t('{{open}} open', { open: jobs.open })}
                  </>
                }
                to="/production"
              />
            )}
            {data.my_production && (
              <Figure
                label={t('My printing this month')}
                value={`${formatQty(data.my_production.sqft)} sq ft`}
                sub={t('{{count}} jobs', { count: data.my_production.jobs })}
                to="/reports/operator-log"
              />
            )}
            {data.low_stock && !data.dues && (
              <Figure
                label={t('Low stock')}
                value={data.low_stock.length}
                sub={t('items below their set level')}
                to="/inventory?low=true"
              />
            )}
          </div>
        )}

        <Grid gap="md">
          {/* -- Work ------------------------------------------------------------------ */}
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Stack gap="md">
              {data?.overdue_jobs && (
                <SectionCard
                  title={t('Jobs to deliver')}
                  description={t('Due today and late, oldest first')}
                  actions={<SeeAll to="/production">{t('Production board')}</SeeAll>}
                  flush
                >
                  {data.overdue_jobs.length === 0 ? (
                    <EmptyState compact title={t('Nothing is late')} />
                  ) : (
                    <DataTable
                      records={data.overdue_jobs}
                      verticalSpacing={8}
                      highlightOnHover
                      onRowClick={() => void navigate('/production')}
                      columns={[
                        {
                          accessor: 'job_no',
                          title: t('Job'),
                          noWrap: true,
                          render: (j) => (
                            <div>
                              <Text size="sm" fw={500}>
                                {j.job_no}
                              </Text>
                              {/* On a phone the other columns fold into this line. */}
                              <Text size="xs" c="dimmed" hiddenFrom="sm" lineClamp={1}>
                                {j.customer} · {j.media} · {j.stage_label}
                              </Text>
                            </div>
                          ),
                        },
                        { accessor: 'customer', title: t('Customer'), visibleMediaQuery: WIDE },
                        { accessor: 'media', title: t('Material'), visibleMediaQuery: WIDE },
                        { accessor: 'stage_label', title: t('Stage'), visibleMediaQuery: WIDE },
                        {
                          accessor: 'deadline',
                          title: t('Due'),
                          textAlign: 'right',
                          noWrap: true,
                          render: (j) => (
                            <Text size="sm" fw={600} c={late(j.deadline) ? 'red.7' : 'amber.8'}>
                              {deadlineLabel(j.deadline)}
                            </Text>
                          ),
                        },
                      ]}
                    />
                  )}
                </SectionCard>
              )}
              {/* No sales chart (front desk): orders to hand over fill this column. */}
              {data?.sales_trend ? <SalesTrendCard data={data.sales_trend} /> : readyCard}
            </Stack>
          </Grid.Col>

          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap="md">
              {jobs && (
                <SectionCard
                  title={t('In production')}
                  actions={<SeeAll to="/production">{t('Open board')}</SeeAll>}
                  flush
                >
                  <div style={{ borderTop: '1px solid var(--ck-border)' }}>
                    {jobs.by_stage.map((s) => (
                      <Link key={s.stage} to="/production" className={classes.stage}>
                        <StageBadge stage={s.stage} full />
                        <strong>{s.count}</strong>
                      </Link>
                    ))}
                  </div>
                </SectionCard>
              )}
              {data?.sales_trend && readyCard}
              {data?.low_stock && (
                <SectionCard
                  title={t('Low stock')}
                  actions={<SeeAll to="/inventory">{t('Inventory')}</SeeAll>}
                  flush
                >
                  {data.low_stock.length === 0 ? (
                    <EmptyState compact title={t('Stock levels are fine')} />
                  ) : (
                    <DataTable
                      records={data.low_stock}
                      noHeader
                      verticalSpacing={8}
                      highlightOnHover
                      onRowClick={({ record }) => void navigate(`/inventory/${record.id}`)}
                      columns={[
                        { accessor: 'name' },
                        {
                          accessor: 'on_hand',
                          textAlign: 'right',
                          render: (i) => (
                            <Text size="sm" className="num">
                              <Text span c="amber.8" fw={600}>
                                {formatQty(i.on_hand)}
                              </Text>{' '}
                              / {formatQty(i.low_stock_level)} {i.unit}
                            </Text>
                          ),
                        },
                      ]}
                    />
                  )}
                </SectionCard>
              )}
            </Stack>
          </Grid.Col>
        </Grid>

        {/* -- Staff attendance (owner) -------------------------------------------- */}
        {can(Perm.STAFF_MANAGE) && <AttendanceRegister withLink />}

        {/* -- Money ------------------------------------------------------------------ */}
        <Grid gap="md">
          {data?.dues_follow_up && data.dues_follow_up.length > 0 && (
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <SectionCard
                title={t('Dues to follow up')}
                description={t('Oldest unpaid first')}
                actions={<SeeAll to="/ledger/balances">{t('All balances')}</SeeAll>}
                flush
              >
                <DataTable
                  records={data.dues_follow_up}
                  idAccessor="customer_id"
                  verticalSpacing={8}
                  highlightOnHover
                  onRowClick={({ record }) => void navigate(`/customers/${record.customer_id}`)}
                  columns={[
                    {
                      accessor: 'name',
                      title: t('Customer'),
                      render: (d) => (
                        <div>
                          <Text size="sm" fw={500}>
                            {d.name}
                          </Text>
                          <Text size="xs" c="dimmed" hiddenFrom="sm">
                            {t('Due since {{date}} BS', { date: d.oldest_due_date_bs })}
                            {d.phone ? ` · ${d.phone}` : ''}
                          </Text>
                        </div>
                      ),
                    },
                    {
                      accessor: 'phone',
                      title: t('Phone'),
                      visibleMediaQuery: WIDE,
                      render: (d) => d.phone || '—',
                    },
                    {
                      accessor: 'oldest_due_date_bs',
                      title: t('Due since'),
                      noWrap: true,
                      visibleMediaQuery: WIDE,
                      render: (d) => `${d.oldest_due_date_bs} BS`,
                    },
                    {
                      accessor: 'balance',
                      title: t('Balance'),
                      textAlign: 'right',
                      render: (d) => <Money value={d.balance} size="sm" c="red.7" fw={600} />,
                    },
                  ]}
                />
              </SectionCard>
            </Grid.Col>
          )}
          {data?.recent_payments && (
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <SectionCard
                title={t('Recent payments')}
                actions={<SeeAll to="/payments">{t('All payments')}</SeeAll>}
                flush
              >
                {data.recent_payments.length === 0 ? (
                  <EmptyState compact title={t('No payments yet')} />
                ) : (
                  <DataTable
                    records={data.recent_payments}
                    verticalSpacing={8}
                    columns={[
                      {
                        accessor: 'customer',
                        title: t('From'),
                        render: (p) => (
                          <div>
                            <Text size="sm" fw={500} lineClamp={1}>
                              {p.customer}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {p.receipt_no}
                              <Text span size="xs" hiddenFrom="sm">
                                {' '}
                                · {p.mode} · {formatDate(p.payment_date)}
                              </Text>
                            </Text>
                          </div>
                        ),
                      },
                      { accessor: 'mode', title: t('Mode'), visibleMediaQuery: WIDE },
                      {
                        accessor: 'payment_date',
                        title: t('Date'),
                        noWrap: true,
                        visibleMediaQuery: WIDE,
                        render: (p) => formatDate(p.payment_date),
                      },
                      {
                        accessor: 'amount',
                        title: t('Amount'),
                        textAlign: 'right',
                        render: (p) => <Money value={p.amount} size="sm" fw={600} />,
                      },
                    ]}
                  />
                )}
              </SectionCard>
            </Grid.Col>
          )}
        </Grid>
        {!data && <ReportSkeleton />}
      </Stack>
    </>
  );
}
