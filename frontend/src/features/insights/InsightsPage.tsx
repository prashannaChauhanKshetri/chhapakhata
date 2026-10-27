import { BarChart } from '@mantine/charts';
import {
  Anchor,
  Box,
  Grid,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import {
  IconCash,
  IconClipboardList,
  IconDiscount,
  IconFileInvoice,
  IconReceipt,
  IconUserPlus,
} from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { apiGet } from '@/api/http';
import type { Insights } from '@/api/types';
import { BarList } from '@/components/BarList';
import { PageHeader } from '@/components/PageHeader';
import {
  PeriodPicker,
  type PeriodValue,
  resolvePeriod,
  usePeriods,
} from '@/components/PeriodPicker';
import { QueryError } from '@/components/QueryError';
import { SectionCard } from '@/components/SectionCard';
import { StatCard } from '@/components/StatCard';
import {
  formatAmount,
  formatNPR,
  formatNPRCompact,
  formatQty,
  plural,
  toNumber,
} from '@/lib/format';

// Two series on one money axis. Validated as a pair (lightness, chroma, colour-blind
// separation, contrast); kept apart from the amber/red used for warnings.
const WORK_COLOR = '#3B5BDB';
const PAID_COLOR = '#0CA678';

/** Share as a percentage, never showing a real amount as "0%". */
function share(part: number, whole: number): string {
  if (whole <= 0 || part <= 0) return '0%';
  const pct = (part / whole) * 100;
  return pct < 0.1 ? 'under 0.1%' : `${formatQty(Math.round(pct * 10) / 10)}%`;
}

function compact(value: number): string {
  if (value >= 1e5) return `${(value / 1e5).toFixed(1).replace(/\.0$/, '')}L`;
  if (value >= 1e3) return `${Math.round(value / 1e3)}K`;
  return String(value);
}

function hours(value: number | null): string {
  if (value === null) return '—';
  if (value < 24) return `${formatQty(value)} h`;
  return `${formatQty(Math.round((value / 24) * 10) / 10)} days`;
}

function TrendCard({ data }: { data: Insights }) {
  const { t } = useTranslation();
  const [view, setView] = useState<'chart' | 'table'>('chart');
  return (
    <SectionCard
      title={
        <div>
          <Text fw={600}>{t('Work done and money collected')}</Text>
          <Text size="sm" c="dimmed">
            {data.granularity === 'day' ? t('Per day') : t('Per BS month')}
          </Text>
        </div>
      }
      actions={
        <SegmentedControl
          size="xs"
          value={view}
          onChange={(v) => setView(v as 'chart' | 'table')}
          data={[
            { value: 'chart', label: t('Chart') },
            { value: 'table', label: t('Table') },
          ]}
          aria-label={t('Show as chart or table')}
        />
      }
    >
      {view === 'chart' ? (
        <BarChart
          h={260}
          data={data.trend}
          dataKey="label"
          series={[
            { name: 'work_done', label: t('Work done'), color: WORK_COLOR },
            { name: 'collected', label: t('Collected'), color: PAID_COLOR },
          ]}
          withLegend
          legendProps={{ verticalAlign: 'top', height: 32 }}
          maxBarWidth={18}
          barProps={{ radius: [4, 4, 0, 0] }}
          barChartProps={{ barGap: 2, barCategoryGap: '24%' }}
          gridAxis="y"
          strokeDasharray="0"
          gridColor="slate.2"
          textColor="slate.5"
          tickLine="none"
          valueFormatter={(v) => formatNPR(v)}
          yAxisProps={{ tickFormatter: compact, width: 44 }}
          xAxisProps={{ interval: 'preserveStartEnd', minTickGap: 16 }}
          tooltipAnimationDuration={120}
          tooltipProps={{ cursor: { fill: 'rgba(148, 163, 184, 0.12)' } }}
        />
      ) : (
        <Box mah={280} style={{ overflowY: 'auto' }}>
          <Table highlightOnHover stickyHeader>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('Period')}</Table.Th>
                <Table.Th ta="right">{t('Work done')}</Table.Th>
                <Table.Th ta="right">{t('Collected')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.trend.map((p) => (
                <Table.Tr key={p.date_from}>
                  <Table.Td>{p.label}</Table.Td>
                  <Table.Td ta="right" className="num">
                    {formatAmount(p.work_done)}
                  </Table.Td>
                  <Table.Td ta="right" className="num">
                    {formatAmount(p.collected)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Box>
      )}
    </SectionCard>
  );
}

export default function InsightsPage() {
  const { t } = useTranslation();
  const { data: periods } = usePeriods();
  const [period, setPeriod] = useState<PeriodValue>({ key: 'this_month', from: null, to: null });
  const resolved = resolvePeriod(period, periods);
  const ready = resolved.key === 'custom' ? !!(resolved.from && resolved.to) : !!resolved.to;
  const query = { from: resolved.from ?? undefined, to: resolved.to ?? undefined };
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: ['insights', query],
    queryFn: () => apiGet<Insights>('/api/v1/insights/', query),
    enabled: ready,
    placeholderData: (previous) => previous,
  });
  const s = data?.summary;
  const p = data?.production;
  const loading = !data;

  return (
    <>
      <PageHeader
        title={t('Insights')}
        description={t(
          'How the shop did over a period: sales, money in, customers, dues and production.',
        )}
        actions={<PeriodPicker value={period} onChange={setPeriod} allowAll={false} />}
      />
      {error ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : (
        <Stack gap="lg" style={{ opacity: isFetching && data ? 0.7 : 1 }}>
          <SimpleGrid cols={{ base: 2, md: 3 }} spacing="sm">
            <StatCard
              label={t('Work done')}
              loading={loading}
              value={formatNPRCompact(s?.work_done)}
              hint={plural(s?.orders ?? 0, t('order'))}
              icon={<IconClipboardList size={18} />}
              accent="blue"
            />
            <StatCard
              label={t('Collected')}
              loading={loading}
              value={formatNPRCompact(s?.collected)}
              icon={<IconCash size={18} />}
              accent="green"
            />
            <StatCard
              label={t('Invoiced')}
              loading={loading}
              value={formatNPRCompact(s?.invoiced)}
              hint={t('Tax invoices only')}
              icon={<IconFileInvoice size={18} />}
              accent="slate"
            />
            <StatCard
              label={t('Average order')}
              loading={loading}
              value={formatNPRCompact(s?.average_order)}
              icon={<IconReceipt size={18} />}
              accent="violet"
            />
            <StatCard
              label={t('Discounts given')}
              loading={loading}
              value={formatNPRCompact(s?.discounts)}
              hint={
                s && toNumber(s.work_done) > 0
                  ? t('{{p}} of work done', {
                      p: share(toNumber(s.discounts), toNumber(s.work_done)),
                    })
                  : undefined
              }
              icon={<IconDiscount size={18} />}
              accent="amber"
            />
            <StatCard
              label={t('New customers')}
              loading={loading}
              value={s?.new_customers ?? 0}
              hint={t('{{q}} open', { q: plural(s?.quotations_open ?? 0, t('quotation')) })}
              icon={<IconUserPlus size={18} />}
              accent="orange"
            />
          </SimpleGrid>

          {data && <TrendCard data={data} />}

          <Grid gap="lg">
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard title={t('Best-selling items')}>
                <BarList
                  empty={t('No orders in this period')}
                  rows={(data?.top_items ?? []).map((i) => ({
                    key: i.name,
                    label: i.name,
                    value: toNumber(i.amount),
                    display: formatNPR(i.amount),
                    hint:
                      toNumber(i.sqft) > 0
                        ? `${formatQty(i.sqft)} sq ft · ${plural(i.orders, t('order'))}`
                        : `${plural(i.pieces, t('piece'))} · ${plural(i.orders, t('order'))}`,
                  }))}
                />
              </SectionCard>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard title={t('Top customers')}>
                <BarList
                  empty={t('No orders in this period')}
                  rows={(data?.top_customers ?? []).map((c) => ({
                    key: c.customer_id,
                    label: c.name,
                    value: toNumber(c.amount),
                    display: formatNPR(c.amount),
                    hint: plural(c.orders, t('order')),
                    to: `/customers/${c.customer_id}`,
                  }))}
                />
              </SectionCard>
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 6 }}>
              <SectionCard
                title={
                  <div>
                    <Text fw={600}>{t('Dues by age')}</Text>
                    <Text size="sm" c="dimmed">
                      {t('Total due {{amount}} on {{date}} BS', {
                        amount: formatNPR(data?.dues_total),
                        date: data?.date_to_bs ?? '',
                      })}
                    </Text>
                  </div>
                }
                actions={
                  <Anchor component={Link} to="/ledger/balances" size="sm">
                    {t('Customer balances')}
                  </Anchor>
                }
              >
                <BarList
                  empty={t('Nobody owes the shop money')}
                  rows={(data?.aging ?? []).map((a) => ({
                    key: a.label,
                    label: t('{{label}} days', { label: a.label }),
                    value: toNumber(a.amount),
                    display: formatNPR(a.amount),
                  }))}
                />
                {(data?.top_dues.length ?? 0) > 0 && (
                  <Table mt="md" verticalSpacing={6} fz="sm">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>{t('Owes the most')}</Table.Th>
                        <Table.Th>{t('Oldest due (BS)')}</Table.Th>
                        <Table.Th ta="right">{t('Balance')}</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {data?.top_dues.map((d) => (
                        <Table.Tr key={d.customer_id}>
                          <Table.Td>
                            <Anchor component={Link} to={`/customers/${d.customer_id}`} size="sm">
                              {d.name}
                            </Anchor>
                          </Table.Td>
                          <Table.Td c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                            {d.oldest_due_date_bs ?? '—'}
                          </Table.Td>
                          <Table.Td ta="right" className="num">
                            {formatAmount(d.balance)}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                )}
              </SectionCard>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Stack gap="lg">
                <SectionCard title={t('Money in by payment mode')}>
                  <BarList
                    empty={t('No payments in this period')}
                    rows={(data?.payment_modes ?? []).map((m) => ({
                      key: m.mode,
                      label: m.mode,
                      value: toNumber(m.amount),
                      display: formatNPR(m.amount),
                      hint: plural(m.count, t('payment')),
                    }))}
                  />
                </SectionCard>
                <SectionCard title={t('Production')}>
                  <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="md">
                    <Figure label={t('Jobs finished')} value={p?.jobs_finished ?? '—'} />
                    <Figure
                      label={t('On time')}
                      value={p?.on_time_percent != null ? `${formatQty(p.on_time_percent)}%` : '—'}
                      tone={
                        p?.on_time_percent != null && p.on_time_percent < 80 ? 'warn' : undefined
                      }
                    />
                    <Figure
                      label={t('Order to ready')}
                      value={hours(p?.average_turnaround_hours ?? null)}
                    />
                    <Figure label={t('Open jobs')} value={p?.open_jobs ?? '—'} />
                    <Figure
                      label={t('Material used')}
                      value={p ? `${formatQty(p.material_used)} sq ft` : '—'}
                    />
                    <Figure
                      label={t('Wastage')}
                      value={p?.wastage_percent != null ? `${formatQty(p.wastage_percent)}%` : '—'}
                      hint={p ? `${formatQty(p.material_wasted)} sq ft` : undefined}
                      tone={
                        p?.wastage_percent != null && p.wastage_percent > 10 ? 'warn' : undefined
                      }
                    />
                  </SimpleGrid>
                </SectionCard>
              </Stack>
            </Grid.Col>
          </Grid>
        </Stack>
      )}
    </>
  );
}

function Figure({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: 'warn';
}) {
  return (
    <div>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Group gap={6} align="baseline">
        <Text fz={20} fw={600} className="num" c={tone === 'warn' ? 'amber.8' : undefined}>
          {value}
        </Text>
        {tone === 'warn' && (
          <Text size="xs" c="amber.8">
            needs attention
          </Text>
        )}
      </Group>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </div>
  );
}
