import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  List,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  ThemeIcon,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconDownload,
  IconFileSpreadsheet,
  IconTableImport,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ensureCsrfCookie, fetchWithTimeout } from '@/api/client';
import { ApiError } from '@/api/errors';
import { FILE_TIMEOUT_MS, openFile } from '@/api/files';
import { withQuery } from '@/api/http';
import type { WorkLogImportResult } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import {
  PeriodPicker,
  type PeriodValue,
  resolvePeriod,
  usePeriods,
} from '@/components/PeriodPicker';
import { SectionCard } from '@/components/SectionCard';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, formatDate, formatQty } from '@/lib/format';
import { Perm } from '@/lib/permissions';

const FIELD_LABELS: Record<string, string> = {
  date: 'Date',
  customer: 'Customer',
  address: 'Address',
  phone: 'Phone',
  item: 'Item',
  height: 'Height',
  width: 'Width',
  quantity: 'Qty',
  sqft: 'Sq ft',
  unit: 'Unit',
  rate: 'Rate',
  amount: 'Amount',
  details: 'Details',
  paid: 'Payment',
  mode: 'Payment mode',
  discount: 'Discount',
  vat: 'VAT',
  balance: 'Balance',
  order_no: 'Order no.',
};

async function uploadWorkLog(file: File, dryRun: boolean, skipErrors: boolean) {
  const body = new FormData();
  body.append('file', file);
  body.append('dry_run', String(dryRun));
  body.append('skip_errors', String(skipErrors));
  const response = await fetchWithTimeout(
    '/api/v1/system/work-log/import/',
    {
      method: 'POST',
      body,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': await ensureCsrfCookie() },
    },
    FILE_TIMEOUT_MS,
  );
  if (!response.ok) throw await ApiError.fromResponse(response);
  return (await response.json()) as WorkLogImportResult;
}

function Figure({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed" fw={500}>
        {label}
      </Text>
      <Text fw={600} className="num">
        {value}
      </Text>
    </div>
  );
}

function MessageTable({
  rows,
  tone,
}: {
  rows: WorkLogImportResult['errors'];
  tone: 'error' | 'warning';
}) {
  const { t } = useTranslation();
  return (
    <ScrollArea.Autosize mah={240}>
      <Table verticalSpacing={4} fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={70}>{t('Row')}</Table.Th>
            <Table.Th>{tone === 'error' ? t('Problem') : t('Note')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((m, i) => (
            <Table.Tr key={`${m.row}-${i}`}>
              <Table.Td className="num">{m.row}</Table.Td>
              <Table.Td>{m.message}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea.Autosize>
  );
}

function ImportResultCard({
  result,
  busy,
  onImport,
}: {
  result: WorkLogImportResult;
  busy: boolean;
  onImport: (skipErrors: boolean) => void;
}) {
  const { t } = useTranslation();
  const hasErrors = result.errors.length > 0;
  const saved = !result.dry_run;
  const nothingNew = result.rows_imported === 0;

  return (
    <Card withBorder padding="md">
      <Stack gap="md">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <ThemeIcon
            variant="light"
            color={saved ? 'green' : hasErrors ? 'amber' : 'slate'}
            size={32}
            radius="md"
          >
            {saved ? <IconCircleCheck size={18} /> : <IconFileSpreadsheet size={18} />}
          </ThemeIcon>
          <div>
            <Text fw={600}>
              {saved
                ? t('Imported {{rows}} rows into {{orders}} orders', {
                    rows: result.rows_imported,
                    orders: result.orders,
                  })
                : nothingNew
                  ? t('Nothing new to import')
                  : t('Ready to import {{rows}} rows as {{orders}} orders', {
                      rows: result.rows_imported,
                      orders: result.orders,
                    })}
            </Text>
            <Text size="sm" c="dimmed">
              {result.file_name} · {t('header on row {{n}}', { n: result.header_row })}
              {result.date_from &&
                ` · ${formatDate(result.date_from)} – ${formatDate(result.date_to)}`}
            </Text>
          </div>
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} spacing="sm">
          <Figure label={t('Rows read')} value={result.rows_read} />
          <Figure label={t('Work amount')} value={formatAmount(result.totals.amount)} />
          <Figure label={t('Discount')} value={formatAmount(result.totals.discount)} />
          <Figure label={t('Paid')} value={formatAmount(result.totals.paid)} />
          <Figure label={t('Balance to ledger')} value={formatAmount(result.totals.balance)} />
          <Figure label={t('Receipts')} value={result.payments} />
        </SimpleGrid>

        {(result.rows_skipped_duplicate > 0 || result.rows_already_in_system > 0) && (
          <Text size="sm" c="dimmed">
            {result.rows_skipped_duplicate > 0 &&
              t('{{n}} rows were imported before and are skipped. ', {
                n: result.rows_skipped_duplicate,
              })}
            {result.rows_already_in_system > 0 &&
              t('{{n}} rows came from ChhapaKhata (they have an order number) and are skipped.', {
                n: result.rows_already_in_system,
              })}
          </Text>
        )}

        <Text size="sm">
          <Text span fw={500}>
            {t('Columns found')}:{' '}
          </Text>
          {Object.entries(result.columns).map(([field, header]) => (
            <Badge key={field} variant="light" color="slate" mr={4} mb={4}>
              {t(FIELD_LABELS[field] ?? field)} ← {header}
            </Badge>
          ))}
        </Text>

        {(result.new_customers.length > 0 || result.matched_customers > 0) && (
          <Text size="sm">
            {t('Customers: {{matched}} already in the system, {{created}} new', {
              matched: result.matched_customers,
              created: result.new_customers.length,
            })}
            {result.new_customers.length > 0 && (
              <Text span c="dimmed">
                {' '}
                ({result.new_customers.slice(0, 12).join(', ')}
                {result.new_customers.length > 12 ? ', …' : ''})
              </Text>
            )}
          </Text>
        )}

        {result.new_items.length > 0 && (
          <Alert color="blue" variant="light" title={t('New rate-card items')}>
            <Text size="sm" mb={4}>
              {t(
                'These items are not on the rate card yet. They will be added with the rate from the sheet; check them under Rate card afterwards.',
              )}
            </Text>
            <List size="sm" spacing={2}>
              {result.new_items.map((item) => (
                <List.Item key={item.name}>
                  {item.name} · Rs {formatQty(item.rate)} /{' '}
                  {item.pricing_unit === 'piece' ? t('piece') : t('sq ft')}
                </List.Item>
              ))}
            </List>
          </Alert>
        )}

        {hasErrors && (
          <Alert
            color="red"
            variant="light"
            icon={<IconAlertTriangle size={18} />}
            title={t('{{n}} rows have problems', { n: result.rows_skipped_error })}
          >
            <Text size="sm" mb="xs">
              {t(
                'Fix these rows in Excel and upload again, or import only the rows without problems.',
              )}
            </Text>
            <MessageTable rows={result.errors} tone="error" />
          </Alert>
        )}

        {result.warnings.length > 0 && (
          <Alert
            color="amber"
            variant="light"
            title={t('{{n}} notes', { n: result.warnings.length })}
          >
            <Text size="sm" mb="xs">
              {t(
                'These rows will be imported as shown in the sheet. Check that the amounts are right.',
              )}
            </Text>
            <MessageTable rows={result.warnings} tone="warning" />
          </Alert>
        )}

        {saved ? (
          <Group gap="sm">
            <Button component={Link} to="/ledger/balances" variant="default">
              {t('Open customer balances')}
            </Button>
            <Button component={Link} to="/orders" variant="default">
              {t('Open orders')}
            </Button>
          </Group>
        ) : (
          !nothingNew && (
            <Group gap="sm">
              {hasErrors ? (
                <Button loading={busy} onClick={() => onImport(true)} color="amber">
                  {t('Import {{n}} good rows, skip {{bad}}', {
                    n: result.rows_imported,
                    bad: result.rows_skipped_error,
                  })}
                </Button>
              ) : (
                <Button
                  leftSection={<IconTableImport size={16} />}
                  loading={busy}
                  onClick={() => onImport(false)}
                >
                  {t('Import {{n}} rows', { n: result.rows_imported })}
                </Button>
              )}
            </Group>
          )
        )}
      </Stack>
    </Card>
  );
}

function WorkLogImport() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<WorkLogImportResult | null>(null);
  const [busy, setBusy] = useState<'check' | 'import' | null>(null);

  const check = async (chosen: File | null) => {
    setFile(chosen);
    setResult(null);
    if (!chosen) return;
    setBusy('check');
    try {
      setResult(await uploadWorkLog(chosen, true, false));
    } catch (error) {
      notifyError(error, t('Could not read the file'));
    } finally {
      setBusy(null);
    }
  };

  const runImport = async (skipErrors: boolean) => {
    if (!file) return;
    setBusy('import');
    try {
      const saved = await uploadWorkLog(file, false, skipErrors);
      setResult(saved);
      if (!saved.dry_run) {
        await client.invalidateQueries();
        notifySuccess(t('Work log imported'));
      }
    } catch (error) {
      notifyError(error, t('Import failed; nothing was saved'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <SectionCard
      title={t('Import the Excel work log')}
      description={t(
        'Bring in the sheet the shop kept before (Date, Particular, Address, Items, Height, Width, Qty, SQFT, Rate, Amount, Details, Payment, Discount, Balance). Rows with the same date and customer become one delivered order; balances go to the customer ledger and each customer’s rates are remembered.',
      )}
    >
      <Stack gap="md">
        <Group gap="sm" align="flex-end" wrap="wrap">
          <FileInput
            label={t('Work log file')}
            placeholder={t('Choose .xlsx or .csv')}
            accept=".xlsx,.xlsm,.csv"
            leftSection={<IconFileSpreadsheet size={16} />}
            value={file}
            onChange={(f) => void check(f)}
            clearable
            w={340}
          />
          <Button
            variant="subtle"
            leftSection={<IconDownload size={16} />}
            onClick={() =>
              void openFile('/api/v1/system/work-log/template/', { download: true }).catch((e) =>
                notifyError(e),
              )
            }
          >
            {t('Blank template')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed">
          {t(
            'The file is checked first and nothing is saved until you press Import. Dates can be BS (2083.04.01) or AD. Uploading the same sheet again only adds new rows.',
          )}
        </Text>
        {busy === 'check' && <Text size="sm">{t('Checking the file…')}</Text>}
        {result && (
          <ImportResultCard result={result} busy={busy === 'import'} onImport={runImport} />
        )}
      </Stack>
    </SectionCard>
  );
}

function WorkLogExport() {
  const { t } = useTranslation();
  const { data: periods } = usePeriods();
  const [period, setPeriod] = useState<PeriodValue>({ key: 'this_fy', from: null, to: null });
  const [busy, setBusy] = useState(false);
  const resolved = resolvePeriod(period, periods);
  const download = async () => {
    setBusy(true);
    try {
      await openFile(
        withQuery('/api/v1/system/work-log/export/', {
          from: resolved.from ?? undefined,
          to: resolved.to ?? undefined,
        }),
        { download: true },
      );
    } catch (error) {
      notifyError(error, t('Could not create the file'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <SectionCard
      title={t('Export the work log')}
      description={t(
        'Download orders in the same Excel layout as the shop’s old sheet: one row per item, with payment, discount and balance.',
      )}
    >
      <Group gap="sm" align="flex-end" wrap="wrap">
        <PeriodPicker value={period} onChange={setPeriod} />
        <Button
          leftSection={<IconDownload size={16} />}
          loading={busy}
          onClick={() => void download()}
        >
          {t('Download Excel')}
        </Button>
      </Group>
    </SectionCard>
  );
}

export function ImportTab() {
  const { t } = useTranslation();
  const { can } = useAuth();
  return (
    <Stack gap="lg">
      {can(Perm.SETTINGS_MANAGE) && <WorkLogImport />}
      {can(Perm.REPORTS_ALL) && <WorkLogExport />}
      <Text size="xs" c="dimmed">
        {t('For a full copy of every table, use')}{' '}
        <Anchor component={Link} to="/settings/backups" size="xs">
          {t('Backups & export')}
        </Anchor>
        .
      </Text>
    </Stack>
  );
}
