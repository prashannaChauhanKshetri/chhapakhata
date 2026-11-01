import {
  Alert,
  Button,
  Card,
  FileInput,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
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

import { openFile } from '@/api/files';
import type { TableImportResult } from '@/api/types';
import { usePeriods } from '@/components/PeriodPicker';
import { SectionCard } from '@/components/SectionCard';
import { notifyError, notifySuccess } from '@/lib/forms';
import { formatAmount, todayISO } from '@/lib/format';

import { ColumnFixer, ColumnsFound } from './ColumnFixer';
import { MessageTable } from './MessageTable';
import { type ColumnChoices, SHEET_TYPES, uploadSheet } from './upload';

export type GoLiveKind = 'customers' | 'rate-card' | 'opening-stock';

interface KindText {
  title: string;
  description: string;
  links: { to: string; label: string }[];
  summary?: { key: string; label: string; money?: boolean }[];
}

const KINDS: Record<GoLiveKind, KindText> = {
  customers: {
    title: 'Import customers and opening balances',
    description:
      'Bring in the customer list with what each one owes (or has paid in advance) on the day you start. Any layout works: a name column plus a balance, or separate Dr and Cr columns. Customers already in the system are not added twice, and anyone who already has entries keeps their balance as it is.',
    links: [
      { to: '/customers', label: 'Open customers' },
      { to: '/ledger/balances', label: 'Open customer balances' },
    ],
    summary: [
      { key: 'opening_due', label: 'Dues brought in', money: true },
      { key: 'opening_advance', label: 'Advances brought in', money: true },
    ],
  },
  'rate-card': {
    title: 'Import the rate card',
    description:
      'Media and add-ons with their rates. Items with the same name are updated, so the sheet can be uploaded again when prices change. Write the unit (sq ft or piece) in its own column or next to the rate, like 60/pc.',
    links: [{ to: '/settings/rate-card', label: 'Open the rate card' }],
  },
  'opening-stock': {
    title: 'Import opening stock',
    description:
      'Stock on hand on the day you start. Rolls need their width and length in feet (and how many); other items need a quantity. An item that already has opening stock is skipped, so uploading the sheet twice does not double it.',
    links: [{ to: '/inventory', label: 'Open inventory' }],
    summary: [{ key: 'rolls', label: 'Rolls' }],
  },
};

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

function ResultCard({
  kind,
  result,
  busy,
  onImport,
  onColumns,
}: {
  kind: GoLiveKind;
  result: TableImportResult;
  busy: 'check' | 'import' | null;
  onImport: (skipErrors: boolean) => void;
  onColumns: (choices: ColumnChoices) => void;
}) {
  const { t } = useTranslation();
  const [fixing, setFixing] = useState(false);
  const text = KINDS[kind];
  const saved = !result.dry_run;
  const hasErrors = result.errors.length > 0;
  const changes = result.created + result.updated;

  if (result.needs_columns) {
    return (
      <Card withBorder>
        <Stack gap="md">
          <Alert color="amber" variant="light" icon={<IconAlertTriangle size={18} />}>
            {result.problem}
          </Alert>
          <ColumnFixer
            headers={result.headers}
            columns={result.columns}
            fields={result.field_choices}
            busy={busy === 'check'}
            onApply={onColumns}
          />
        </Stack>
      </Card>
    );
  }

  return (
    <Card withBorder>
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
                ? t('Imported: {{created}} added, {{updated}} updated', {
                    created: result.created,
                    updated: result.updated,
                  })
                : changes === 0
                  ? t('Nothing new to import')
                  : t('Ready: {{created}} to add, {{updated}} to update', {
                      created: result.created,
                      updated: result.updated,
                    })}
            </Text>
            <Text size="sm" c="dimmed">
              {result.file_name}
              {result.sheets.length > 1 && ` · ${t('sheets')}: ${result.sheets.join(', ')}`}
              {' · '}
              {t('header on row {{n}}', { n: result.header_row })}
            </Text>
          </div>
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          <Figure label={t('Rows read')} value={result.rows_read} />
          <Figure label={saved ? t('Added') : t('To add')} value={result.created} />
          <Figure label={saved ? t('Updated') : t('To update')} value={result.updated} />
          <Figure label={t('Skipped')} value={result.skipped} />
          {text.summary
            ?.filter((s) => result.summary[s.key])
            .map((s) => (
              <Figure
                key={s.key}
                label={t(s.label)}
                value={s.money ? formatAmount(result.summary[s.key]) : result.summary[s.key]}
              />
            ))}
        </SimpleGrid>

        {fixing ? (
          <ColumnFixer
            headers={result.headers}
            columns={result.columns}
            fields={result.field_choices}
            busy={busy === 'check'}
            onApply={(choices) => {
              setFixing(false);
              onColumns(choices);
            }}
            onCancel={() => setFixing(false)}
          />
        ) : (
          <Group gap="xs" align="flex-start" wrap="nowrap">
            <div style={{ flex: 1 }}>
              <ColumnsFound columns={result.columns} fields={result.field_choices} />
            </div>
            {!saved && (
              <Button size="compact-sm" variant="subtle" onClick={() => setFixing(true)}>
                {t('Change columns')}
              </Button>
            )}
          </Group>
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
            <MessageTable rows={result.warnings} tone="warning" />
          </Alert>
        )}

        {saved ? (
          <Group gap="sm">
            {text.links.map((link) => (
              <Button key={link.to} component={Link} to={link.to} variant="default">
                {t(link.label)}
              </Button>
            ))}
          </Group>
        ) : (
          changes > 0 && (
            <Group gap="sm">
              {hasErrors ? (
                <Button loading={busy === 'import'} onClick={() => onImport(true)} color="amber">
                  {t('Import {{n}} good rows, skip {{bad}}', {
                    n: changes,
                    bad: result.rows_skipped_error,
                  })}
                </Button>
              ) : (
                <Button
                  leftSection={<IconTableImport size={16} />}
                  loading={busy === 'import'}
                  onClick={() => onImport(false)}
                >
                  {t('Import {{n}} rows', { n: changes })}
                </Button>
              )}
            </Group>
          )
        )}
      </Stack>
    </Card>
  );
}

/** Upload, check and import one kind of go-live sheet. */
export function GoLiveImport({ kind }: { kind: GoLiveKind }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const text = KINDS[kind];
  const url = `/api/v1/system/import/${kind}/`;
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<ColumnChoices | null>(null);
  // Balances carried in from last year: default to the day last fiscal year closed.
  const { data: periods } = usePeriods();
  const lastYearEnd = periods?.find((p) => p.key === 'last_fy')?.date_to ?? null;
  const [chosenAsOf, setAsOf] = useState<string | null>(null);
  const asOf = chosenAsOf ?? lastYearEnd;
  const [result, setResult] = useState<TableImportResult | null>(null);
  const [busy, setBusy] = useState<'check' | 'import' | null>(null);

  const check = async (chosen: File | null, choices: ColumnChoices | null) => {
    setFile(chosen);
    setColumns(choices);
    if (!choices) setResult(null);
    if (!chosen) return;
    setBusy('check');
    try {
      setResult(
        await uploadSheet<TableImportResult>(url, chosen, { dryRun: true, columns: choices, asOf }),
      );
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
      const saved = await uploadSheet<TableImportResult>(url, file, {
        dryRun: false,
        skipErrors,
        columns,
        asOf,
      });
      setResult(saved);
      if (!saved.dry_run) {
        await client.invalidateQueries();
        notifySuccess(t('Imported'));
      }
    } catch (error) {
      notifyError(error, t('Import failed; nothing was saved'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <SectionCard title={t(text.title)} description={t(text.description)}>
      <Stack gap="md">
        <Group gap="sm" align="flex-end" wrap="wrap">
          <FileInput
            label={t('Excel or CSV file')}
            placeholder={t('Choose a file')}
            accept={SHEET_TYPES}
            leftSection={<IconFileSpreadsheet size={16} />}
            value={file}
            onChange={(f) => void check(f, null)}
            clearable
            w={300}
          />
          {kind === 'customers' && (
            <DatePickerInput
              label={t('Balances as on')}
              description={t('Last year’s closing day')}
              valueFormat="D MMM YYYY"
              maxDate={todayISO()}
              value={asOf}
              onChange={(value) => setAsOf(value)}
              w={170}
            />
          )}
          <Button
            variant="subtle"
            leftSection={<IconDownload size={16} />}
            onClick={() =>
              void openFile(`${url}template/`, { download: true }).catch((e) => notifyError(e))
            }
          >
            {t('Sample sheet')}
          </Button>
        </Group>
        {busy === 'check' && <Text size="sm">{t('Checking the file…')}</Text>}
        {result && (
          <ResultCard
            kind={kind}
            result={result}
            busy={busy}
            onImport={(skip) => void runImport(skip)}
            onColumns={(choices) => void check(file, choices)}
          />
        )}
      </Stack>
    </SectionCard>
  );
}
