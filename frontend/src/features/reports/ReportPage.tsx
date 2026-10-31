import { Button, Card, Group, Loader, Select, SimpleGrid, Stack, Table, Text } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconFileSpreadsheet, IconPrinter } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { openFile } from '@/api/files';
import { apiGet, withQuery } from '@/api/http';
import type { DateConversion, Report, ReportColumn, ReportInfo, User } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { EmptyState } from '@/components/EmptyState';
import { PageHeader } from '@/components/PageHeader';
import { QueryError } from '@/components/QueryError';
import { ReportSkeleton } from '@/components/Skeletons';
import { notifyError } from '@/lib/forms';
import { formatAmount, formatDate, formatQty } from '@/lib/format';
import { Perm } from '@/lib/permissions';

function cell(value: string | number | null | undefined, column: ReportColumn): string {
  if (value === null || value === undefined || value === '') return '';
  switch (column.kind) {
    case 'money':
      return formatAmount(value);
    case 'sqft':
    case 'number':
      return formatQty(value);
    case 'percent':
      return `${formatQty(value)}%`;
    case 'date':
      return formatDate(String(value));
    default:
      return String(value);
  }
}

const NUMERIC = new Set(['money', 'sqft', 'number', 'percent']);
const iso = (d: dayjs.Dayjs) => d.format('YYYY-MM-DD');

export default function ReportPage() {
  const { t } = useTranslation();
  const { slug = '' } = useParams();
  const { can } = useAuth();
  const today = iso(dayjs());
  const { data: list } = useQuery({
    queryKey: ['reports'],
    queryFn: () => apiGet<ReportInfo[]>('/api/v1/reports/'),
  });
  const { data: bsToday } = useQuery({
    queryKey: ['utils', 'today'],
    queryFn: () => apiGet<DateConversion>('/api/v1/utils/date/'),
    staleTime: 600_000,
  });
  const info = list?.find((r) => r.slug === slug);
  const usesRange =
    info?.date_range ??
    ['monthly-sales', 'collections', 'material-vs-sales', 'operator-log'].includes(slug);
  const usesDay = ['daily-sales', 'pending-dues'].includes(slug);

  const [day, setDay] = useState<string | null>(today);
  const [range, setRange] = useState<[string | null, string | null]>([null, null]);
  const [operator, setOperator] = useState<string | null>(null);
  const showOperator = slug === 'operator-log' && can(Perm.REPORTS_ALL);
  const { data: operators = [] } = useQuery({
    queryKey: ['users', 'operators'],
    queryFn: () => apiGet<User[]>('/api/v1/users/operators/'),
    enabled: showOperator,
  });

  const params: Record<string, string | undefined> = usesRange
    ? { from: range[0] ?? undefined, to: range[1] ?? undefined, operator: operator ?? undefined }
    : usesDay
      ? { date: day ?? undefined }
      : {};
  const rangeComplete = !usesRange || (range[0] && range[1]) || (!range[0] && !range[1]);

  const {
    data: report,
    error,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['report', slug, params],
    queryFn: () => apiGet<Report>(`/api/v1/reports/${slug}/`, params),
    enabled: !!rangeComplete,
    placeholderData: (previous) => previous,
  });

  const presets = [
    { label: t('This BS month'), from: bsToday?.bs_month_start, to: today },
    { label: t('Last 7 days'), from: iso(dayjs().subtract(6, 'day')), to: today },
    { label: t('Last 30 days'), from: iso(dayjs().subtract(29, 'day')), to: today },
  ];

  const download = (kind: 'pdf' | 'xlsx') =>
    openFile(withQuery(`/api/v1/reports/${slug}/`, { ...params, export: kind }), {
      download: kind === 'xlsx',
    }).catch((e) => notifyError(e, t('Could not create the file')));

  return (
    <>
      <PageHeader
        back={{ to: '/reports', label: t('Reports') }}
        title={report?.title ?? info?.title ?? t('Report')}
        description={report?.period}
        actions={
          <>
            <Button
              variant="default"
              leftSection={<IconPrinter size={16} />}
              onClick={() => void download('pdf')}
            >
              {t('Print / PDF')}
            </Button>
            <Button
              variant="default"
              leftSection={<IconFileSpreadsheet size={16} />}
              onClick={() => void download('xlsx')}
            >
              {t('Excel')}
            </Button>
          </>
        }
      />
      {(usesRange || usesDay) && (
        <Card mb="lg" padding="md">
          <Group gap="sm" align="flex-end" wrap="wrap">
            {usesDay && (
              <DatePickerInput
                label={slug === 'pending-dues' ? t('As of') : t('Day')}
                valueFormat="ddd D MMM YYYY"
                maxDate={today}
                value={day}
                onChange={(v) => setDay(v as string | null)}
                w={220}
              />
            )}
            {usesRange && (
              <>
                <DatePickerInput
                  type="range"
                  label={t('Period')}
                  placeholder={t('This BS month')}
                  clearable
                  valueFormat="D MMM YYYY"
                  maxDate={today}
                  value={range}
                  onChange={(v) => setRange(v as [string | null, string | null])}
                  w={280}
                />
                <Group gap={6}>
                  {presets.map((p) => (
                    <Button
                      key={p.label}
                      size="xs"
                      variant="default"
                      disabled={!p.from}
                      onClick={() => setRange([p.from ?? null, p.to])}
                    >
                      {p.label}
                    </Button>
                  ))}
                </Group>
              </>
            )}
            {showOperator && (
              <Select
                label={t('Operator')}
                placeholder={t('All operators')}
                clearable
                w={200}
                data={operators.map((o) => ({
                  value: String(o.id),
                  label: o.full_name || o.username,
                }))}
                value={operator}
                onChange={setOperator}
              />
            )}
            {isFetching && report && <Loader size="xs" color="slate.4" mb={10} />}
          </Group>
        </Card>
      )}

      {error ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : !report ? (
        <ReportSkeleton />
      ) : (
        <Stack gap="lg">
          {report.summary.length > 0 && (
            <SimpleGrid
              cols={{
                base: 1,
                xs: 2,
                md: Math.min(report.summary.length, 3),
                lg: Math.min(report.summary.length, 5),
              }}
              spacing="md"
            >
              {report.summary.map((m) => (
                <Card key={m.label} padding="md">
                  <Text size="sm" c="dimmed" fw={500}>
                    {t(m.label)}
                  </Text>
                  <Text fz={22} fw={600}>
                    {m.kind === 'money'
                      ? `Rs. ${cell(m.value, { key: '', label: '', kind: 'money' })}`
                      : cell(m.value, { key: '', label: '', kind: m.kind })}
                    {m.kind === 'sqft' ? ' sq ft' : ''}
                  </Text>
                </Card>
              ))}
            </SimpleGrid>
          )}
          {report.tables.map((table) => (
            <Card key={table.title} padding={0}>
              <Text fw={600} px="lg" pt="md" pb="sm">
                {t(table.title)}
              </Text>
              {table.rows.length === 0 ? (
                <EmptyState compact title={t(table.empty_message)} />
              ) : (
                <Table.ScrollContainer minWidth={table.columns.length * 120}>
                  <Table highlightOnHover verticalSpacing="xs">
                    <Table.Thead>
                      <Table.Tr>
                        {table.columns.map((c) => (
                          <Table.Th key={c.key} ta={NUMERIC.has(c.kind) ? 'right' : 'left'}>
                            {t(c.label)}
                          </Table.Th>
                        ))}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {table.rows.map((row, i) => (
                        <Table.Tr key={i}>
                          {table.columns.map((c) => (
                            <Table.Td
                              key={c.key}
                              ta={NUMERIC.has(c.kind) ? 'right' : 'left'}
                              className={NUMERIC.has(c.kind) ? 'num' : undefined}
                            >
                              {cell(row[c.key], c)}
                            </Table.Td>
                          ))}
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                    {table.totals && (
                      <Table.Tfoot>
                        <Table.Tr bg="slate.0">
                          {table.columns.map((c) => (
                            <Table.Td
                              key={c.key}
                              fw={600}
                              ta={NUMERIC.has(c.kind) ? 'right' : 'left'}
                              className={NUMERIC.has(c.kind) ? 'num' : undefined}
                            >
                              {cell(table.totals?.[c.key], c)}
                            </Table.Td>
                          ))}
                        </Table.Tr>
                      </Table.Tfoot>
                    )}
                  </Table>
                </Table.ScrollContainer>
              )}
            </Card>
          ))}
        </Stack>
      )}
    </>
  );
}
