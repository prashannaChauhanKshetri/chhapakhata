import { ScrollArea, Table } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { ImportMessage } from '@/api/types';

/** Problems or notes per row; a Sheet column appears when the file had several sheets. */
export function MessageTable({ rows, tone }: { rows: ImportMessage[]; tone: 'error' | 'warning' }) {
  const { t } = useTranslation();
  const withSheet = rows.some((m) => m.sheet);
  return (
    <ScrollArea.Autosize mah={240}>
      <Table verticalSpacing={4} fz="sm">
        <Table.Thead>
          <Table.Tr>
            {withSheet && <Table.Th w={110}>{t('Sheet')}</Table.Th>}
            <Table.Th w={70}>{t('Row')}</Table.Th>
            <Table.Th>{tone === 'error' ? t('Problem') : t('Note')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((m, i) => (
            <Table.Tr key={`${m.sheet}-${m.row}-${i}`}>
              {withSheet && <Table.Td>{m.sheet}</Table.Td>}
              <Table.Td className="num">{m.row}</Table.Td>
              <Table.Td>{m.message}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea.Autosize>
  );
}
