import { BarChart } from '@mantine/charts';
import { Box, Group, SegmentedControl, Table, Text } from '@mantine/core';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Dashboard } from '@/api/types';
import { SectionCard } from '@/components/SectionCard';
import { formatAmount, formatNPR } from '@/lib/format';

type Point = NonNullable<Dashboard['sales_trend']>[number];

/** Axis ticks: compact from 1,000 up (0 / 5K / 1.2L). */
function compact(value: number): string {
  if (value >= 1e5) return `${(value / 1e5).toFixed(1).replace(/\.0$/, '')}L`;
  if (value >= 1e3) return `${Math.round(value / 1e3)}K`;
  return String(value);
}

/** Daily invoiced sales for the last 30 days: one series, so no legend box. */
export function SalesTrendCard({ data }: { data: Point[] }) {
  const { t } = useTranslation();
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const rows = useMemo(
    () => data.map((p) => ({ ...p, day: dayjs(p.date).format('D MMM') })),
    [data],
  );
  const total = data.reduce((sum, p) => sum + p.total, 0);

  return (
    <SectionCard
      title={
        <div>
          <Text fw={600}>{t('Sales, last 30 days')}</Text>
          <Text size="sm" c="dimmed">
            {t('Invoiced per day')} · {t('Total')} {formatNPR(total)}
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
          aria-label={t('Show sales as chart or table')}
        />
      }
    >
      {view === 'chart' ? (
        <BarChart
          h={240}
          data={rows}
          dataKey="day"
          series={[{ name: 'total', label: t('Sales'), color: 'slate.6' }]}
          maxBarWidth={24}
          barProps={{ radius: [4, 4, 0, 0] }}
          gridAxis="y"
          strokeDasharray="0"
          gridColor="slate.2"
          textColor="slate.5"
          tickLine="none"
          withLegend={false}
          valueFormatter={(v) => formatNPR(v)}
          yAxisProps={{ tickFormatter: compact, width: 44 }}
          xAxisProps={{ interval: 'preserveStartEnd', minTickGap: 24 }}
          tooltipAnimationDuration={120}
          tooltipProps={{ cursor: { fill: 'rgba(148, 163, 184, 0.12)' } }}
        />
      ) : (
        <Box mah={260} style={{ overflowY: 'auto' }}>
          <Table striped={false} highlightOnHover stickyHeader>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('Date')}</Table.Th>
                <Table.Th>{t('Miti (BS)')}</Table.Th>
                <Table.Th ta="right">{t('Sales')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {[...data].reverse().map((p) => (
                <Table.Tr key={p.date}>
                  <Table.Td>{dayjs(p.date).format('ddd D MMM')}</Table.Td>
                  <Table.Td>{p.date_bs}</Table.Td>
                  <Table.Td ta="right" className="num">
                    {formatAmount(p.total)}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Box>
      )}
      <Group justify="flex-end" mt={4}>
        <Text size="xs" c="dimmed">
          {t('Cancelled invoices are excluded.')}
        </Text>
      </Group>
    </SectionCard>
  );
}
