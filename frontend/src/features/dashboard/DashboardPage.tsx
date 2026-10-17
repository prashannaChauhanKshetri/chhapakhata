import {
  Alert,
  Anchor,
  Badge,
  Button,
  Grid,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Text,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCash,
  IconClockExclamation,
  IconDatabaseExclamation,
  IconFileInvoice,
  IconPackage,
  IconPlus,
  IconReceipt2,
  IconUsers,
} from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/http';
import type { Dashboard } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { EmptyState } from '@/components/EmptyState';
import { Money } from '@/components/Money';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { SectionCard } from '@/components/SectionCard';
import { StatCard } from '@/components/StatCard';
import { StageBadge } from '@/components/StatusBadge';
import { deadlineLabel, formatDate, formatNPRCompact, formatQty } from '@/lib/format';
import { Perm } from '@/lib/permissions';

import { SalesTrendCard } from './SalesTrendCard';

export default function DashboardPage() {
  const { t } = useTranslation();
  const { user, can } = useAuth();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiGet<Dashboard>('/api/v1/dashboard/'),
    refetchInterval: 60_000,
    placeholderData: (previous) => previous,
  });

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return t('Good morning');
    if (hour < 17) return t('Good afternoon');
    return t('Good evening');
  })();

  if (error) return <QueryError error={error} onRetry={() => void refetch()} />;

  const jobs = data?.jobs;
  const maxStage = Math.max(1, ...(jobs?.by_stage.map((s) => s.count) ?? [1]));

  return (
    <>
      <PageHeader
        title={`${greeting}, ${user?.first_name || user?.username}`}
        description={data ? `${data.date_bs} BS · ${formatDate(data.date)}` : undefined}
        actions={
          <>
            {can(Perm.PAYMENTS_RECEIVE) && (
              <Button
                component={Link}
                to="/payments?receive=1"
                variant="default"
                leftSection={<IconReceipt2 size={16} />}
              >
                {t('Receive payment')}
              </Button>
            )}
            {can(Perm.ORDERS_MANAGE) && (
              <Button component={Link} to="/orders/new" leftSection={<IconPlus size={16} />}>
                {t('New order')}
              </Button>
            )}
          </>
        }
      />

      <Stack gap="lg">
        {data?.backup?.is_stale && (
          <Alert
            color="amber"
            icon={<IconDatabaseExclamation size={18} />}
            title={t('Backup needs attention')}
          >
            <Group justify="space-between" gap="sm">
              <Text size="sm">
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

        <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }} spacing="md">
          {data?.today !== undefined || isPending ? (
            <>
              <StatCard
                label={t("Today's sales")}
                value={formatNPRCompact(data?.today?.sales)}
                hint={
                  data?.today ? t('{{count}} invoices', { count: data.today.invoices }) : undefined
                }
                icon={<IconFileInvoice size={18} />}
                to={can(Perm.INVOICES_VIEW) ? '/invoices' : undefined}
                loading={isPending}
              />
              <StatCard
                label={t('Collected today')}
                value={formatNPRCompact(data?.today?.collections)}
                hint={
                  data?.today ? t('{{count}} payments', { count: data.today.payments }) : undefined
                }
                icon={<IconCash size={18} />}
                to={can(Perm.PAYMENTS_VIEW) ? '/payments' : undefined}
                loading={isPending}
              />
            </>
          ) : null}
          {data?.dues && (
            <StatCard
              label={t('Pending dues')}
              value={formatNPRCompact(data.dues.total)}
              hint={t('{{count}} customers · {{amount}} over 90 days', {
                count: data.dues.customers,
                amount: formatNPRCompact(data.dues.over_90_days),
              })}
              icon={<IconUsers size={18} />}
              to="/reports/pending-dues"
              tone={Number(data.dues.over_90_days) > 0 ? 'warning' : 'default'}
            />
          )}
          {jobs && (
            <StatCard
              label={t('Jobs due today')}
              value={jobs.due_today}
              hint={
                jobs.overdue > 0 ? (
                  <>
                    <Text span size="xs" c="red.7" fw={600}>
                      {t('{{count}} overdue', { count: jobs.overdue })}
                    </Text>
                    {' · '}
                    {t('{{open}} open', { open: jobs.open })}
                  </>
                ) : (
                  t('{{open}} open jobs', { open: jobs.open })
                )
              }
              icon={<IconClockExclamation size={18} />}
              to="/production"
            />
          )}
          {data?.my_production && (
            <StatCard
              label={t('My printing this month')}
              value={`${formatQty(data.my_production.sqft)} sq ft`}
              hint={t('{{count}} jobs', { count: data.my_production.jobs })}
              to="/reports/operator-log"
            />
          )}
          {data?.low_stock && !data.dues && (
            <StatCard
              label={t('Low stock')}
              value={data.low_stock.length}
              hint={t('items below their set level')}
              icon={<IconPackage size={18} />}
              to="/inventory?low=true"
              tone={data.low_stock.length > 0 ? 'warning' : 'default'}
            />
          )}
        </SimpleGrid>

        <Grid gap="md">
          {data?.sales_trend && (
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <SalesTrendCard data={data.sales_trend} />
            </Grid.Col>
          )}
          {jobs && (
            <Grid.Col span={{ base: 12, lg: data?.sales_trend ? 4 : 6 }}>
              <SectionCard
                title={t('Production')}
                actions={
                  <Anchor component={Link} to="/production" size="sm">
                    {t('Open board')}
                  </Anchor>
                }
              >
                <Stack gap="sm">
                  {jobs.by_stage.map((s) => (
                    <div key={s.stage}>
                      <Group justify="space-between" mb={4}>
                        <StageBadge stage={s.stage} full />
                        <Text size="sm" fw={600}>
                          {s.count}
                        </Text>
                      </Group>
                      <Progress
                        value={(s.count / maxStage) * 100}
                        color="slate.5"
                        size="sm"
                        radius="xl"
                        aria-hidden
                      />
                    </div>
                  ))}
                </Stack>
              </SectionCard>
            </Grid.Col>
          )}

          {data?.overdue_jobs && (
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard title={t('Due today and overdue')}>
                {data.overdue_jobs.length === 0 ? (
                  <EmptyState
                    compact
                    title={t('Nothing is late')}
                    description={t('Every open job is on schedule.')}
                  />
                ) : (
                  <Stack gap={0}>
                    {data.overdue_jobs.map((job) => {
                      const late = job.deadline !== null && new Date(job.deadline) < new Date();
                      return (
                        <Group
                          key={job.id}
                          justify="space-between"
                          py={8}
                          wrap="nowrap"
                          style={{ borderBottom: '1px solid var(--ck-border)' }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <Text size="sm" fw={500} lineClamp={1}>
                              {job.job_no} · {job.customer}
                            </Text>
                            <Text size="xs" c="dimmed" lineClamp={1}>
                              {job.media} · {job.stage_label}
                            </Text>
                          </div>
                          <Badge
                            color={late ? 'red' : 'amber'}
                            variant="light"
                            style={{ flex: 'none' }}
                          >
                            {deadlineLabel(job.deadline)}
                          </Badge>
                        </Group>
                      );
                    })}
                  </Stack>
                )}
              </SectionCard>
            </Grid.Col>
          )}

          {data?.ready_orders && (
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard title={t('Ready for collection')}>
                {data.ready_orders.length === 0 ? (
                  <EmptyState
                    compact
                    title={t('No orders waiting')}
                    description={t('Finished orders appear here until delivered.')}
                  />
                ) : (
                  <Stack gap={0}>
                    {data.ready_orders.map((o) => (
                      <Group
                        key={o.id}
                        justify="space-between"
                        py={8}
                        wrap="nowrap"
                        style={{ borderBottom: '1px solid var(--ck-border)' }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <Anchor component={Link} to={`/orders/${o.id}`} size="sm" fw={500}>
                            {o.order_no}
                          </Anchor>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {o.customer} · {o.phone}
                          </Text>
                        </div>
                        <Money value={o.total} size="sm" />
                      </Group>
                    ))}
                  </Stack>
                )}
              </SectionCard>
            </Grid.Col>
          )}

          {data?.dues_follow_up && data.dues_follow_up.length > 0 && (
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard
                title={
                  <div>
                    <Text fw={600}>{t('Dues to follow up')}</Text>
                    <Text size="sm" c="dimmed">
                      {t('Oldest unpaid first')}
                    </Text>
                  </div>
                }
                actions={
                  <Anchor component={Link} to="/ledger/balances" size="sm">
                    {t('All balances')}
                  </Anchor>
                }
              >
                <Stack gap={0}>
                  {data.dues_follow_up.map((d) => (
                    <Group
                      key={d.customer_id}
                      justify="space-between"
                      py={8}
                      wrap="nowrap"
                      style={{ borderBottom: '1px solid var(--ck-border)' }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <Anchor
                          component={Link}
                          to={`/customers/${d.customer_id}`}
                          size="sm"
                          fw={500}
                        >
                          {d.name}
                        </Anchor>
                        <Text size="xs" c="dimmed" lineClamp={1}>
                          {t('Due since {{date}} BS', { date: d.oldest_due_date_bs })}
                          {d.phone ? ` · ${d.phone}` : ''}
                        </Text>
                      </div>
                      <Money value={d.balance} size="sm" c="red.7" />
                    </Group>
                  ))}
                </Stack>
              </SectionCard>
            </Grid.Col>
          )}

          {data?.recent_payments && (
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard
                title={t('Recent payments')}
                actions={
                  <Anchor component={Link} to="/payments" size="sm">
                    {t('All payments')}
                  </Anchor>
                }
              >
                {data.recent_payments.length === 0 ? (
                  <EmptyState compact title={t('No payments yet')} />
                ) : (
                  <Stack gap={0}>
                    {data.recent_payments.map((p) => (
                      <Group
                        key={p.id}
                        justify="space-between"
                        py={8}
                        wrap="nowrap"
                        style={{ borderBottom: '1px solid var(--ck-border)' }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500} lineClamp={1}>
                            {p.customer}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {p.receipt_no} · {p.mode} · {formatDate(p.payment_date)}
                          </Text>
                        </div>
                        <Money value={p.amount} size="sm" />
                      </Group>
                    ))}
                  </Stack>
                )}
              </SectionCard>
            </Grid.Col>
          )}

          {data?.low_stock && (
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard
                title={t('Low stock')}
                actions={
                  <Anchor component={Link} to="/inventory" size="sm">
                    {t('Inventory')}
                  </Anchor>
                }
              >
                {data.low_stock.length === 0 ? (
                  <EmptyState
                    compact
                    title={t('Stock levels are fine')}
                    description={t('Nothing is below its low-stock level.')}
                  />
                ) : (
                  <Stack gap={0}>
                    {data.low_stock.map((item) => (
                      <Group
                        key={item.id}
                        justify="space-between"
                        py={8}
                        wrap="nowrap"
                        style={{ borderBottom: '1px solid var(--ck-border)' }}
                      >
                        <Group gap={8} wrap="nowrap">
                          <IconAlertTriangle
                            size={16}
                            color="var(--mantine-color-amber-7)"
                            aria-hidden
                          />
                          <Anchor component={Link} to={`/inventory/${item.id}`} size="sm" fw={500}>
                            {item.name}
                          </Anchor>
                        </Group>
                        <Text size="sm" className="num">
                          {formatQty(item.on_hand)} / {formatQty(item.low_stock_level)} {item.unit}
                        </Text>
                      </Group>
                    ))}
                  </Stack>
                )}
              </SectionCard>
            </Grid.Col>
          )}
        </Grid>
      </Stack>
    </>
  );
}
