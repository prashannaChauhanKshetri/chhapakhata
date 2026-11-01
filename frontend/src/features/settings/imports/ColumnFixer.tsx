import { Badge, Button, Group, Select, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconColumns } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { ImportField } from '@/api/types';

import { type ColumnChoices, choicesFrom } from './upload';

/** The columns the server recognised, shown as "field ← header" badges. */
export function ColumnsFound({
  columns,
  fields,
}: {
  columns: Record<string, string>;
  fields: ImportField[];
}) {
  const { t } = useTranslation();
  const label = (field: string) => fields.find((f) => f.field === field)?.label ?? field;
  return (
    <Text size="sm" component="div">
      <Text span fw={500}>
        {t('Columns found')}:{' '}
      </Text>
      {Object.entries(columns).map(([field, header]) => (
        <Badge key={field} variant="light" color="slate" mr={4} mb={4}>
          {t(label(field))} ← {header}
        </Badge>
      ))}
    </Text>
  );
}

/**
 * Lets the person importing say which column holds what, when the automatic
 * guess is wrong or no header was recognised. One field per column.
 */
export function ColumnFixer({
  headers,
  columns,
  fields,
  busy,
  onApply,
  onCancel,
}: {
  headers: string[];
  columns: Record<string, string>;
  fields: ImportField[];
  busy: boolean;
  onApply: (choices: ColumnChoices) => void;
  onCancel?: () => void;
}) {
  const { t } = useTranslation();
  const [choices, setChoices] = useState<ColumnChoices>(() => choicesFrom(columns, headers));
  const options = [
    { value: '', label: t('Not used') },
    ...fields.map((f) => ({ value: f.field, label: t(f.label) })),
  ];
  const choose = (header: string, field: string) =>
    setChoices((current) => {
      const next = { ...current };
      // A field can come from one column only.
      if (field) for (const h of Object.keys(next)) if (next[h] === field) next[h] = '';
      next[header] = field;
      return next;
    });

  return (
    <Stack gap="sm">
      <Group gap={6}>
        <IconColumns size={16} />
        <Text size="sm" fw={500}>
          {t('Which column holds what?')}
        </Text>
      </Group>
      <Text size="sm" c="dimmed">
        {t(
          'Each box is a column heading from your sheet. Choose what it holds, or “Not used”, then check the file again.',
        )}
      </Text>
      <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="sm">
        {headers.map((header) => (
          <Select
            key={header}
            label={header}
            data={options}
            value={choices[header] ?? ''}
            onChange={(value) => choose(header, value ?? '')}
            allowDeselect={false}
            comboboxProps={{ withinPortal: true }}
          />
        ))}
      </SimpleGrid>
      <Group gap="sm">
        <Button loading={busy} onClick={() => onApply(choices)}>
          {t('Check again with these columns')}
        </Button>
        {onCancel && (
          <Button variant="subtle" color="slate" onClick={onCancel}>
            {t('Cancel')}
          </Button>
        )}
      </Group>
    </Stack>
  );
}
