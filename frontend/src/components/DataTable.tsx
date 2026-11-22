import { type MantineTheme, Pagination, Text, useMantineTheme } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import {
  DataTable as BaseDataTable,
  type DataTableColumn,
  type DataTableProps,
  getRecordId,
  getValueAtPath,
  humanize,
} from 'mantine-datatable';
import { type CSSProperties, type ReactNode, useState } from 'react';

import classes from './DataTable.module.css';
import { TableSkeleton } from './Skeletons';

/** Below this width a row of many columns no longer fits, so rows become cards. */
const PHONE = '(max-width: 47.99em)';

type AppDataTableProps<T> = DataTableProps<T> & {
  /** On phones, rows show as cards unless this is 'table' (for narrow tables that fit). */
  phone?: 'cards' | 'table';
};

/**
 * The app's data table: skeleton rows, not a spinner, while records load. On a
 * phone each row becomes a card, so no column is cut off at the screen edge.
 */
export function DataTable<T>({ phone = 'cards', ...props }: AppDataTableProps<T>) {
  const isPhone = useMediaQuery(PHONE, false, { getInitialValueInEffect: false });
  if (isPhone && phone === 'cards' && props.columns) {
    return <PhoneCards<T> {...props} />;
  }
  // The props type is a union that forbids customLoader alongside spinner
  // options; the app never sets those, so replacing the loader is safe.
  const withSkeleton = {
    ...props,
    customLoader: <TableSkeleton />,
    loaderBackgroundBlur: 0,
  } as DataTableProps<T>;
  return <BaseDataTable<T> {...withSkeleton} />;
}

function visible<T>(column: DataTableColumn<T>, theme: MantineTheme): boolean {
  if (column.hidden) return false;
  const query = column.visibleMediaQuery;
  if (!query) return true;
  return window.matchMedia(typeof query === 'function' ? query(theme) : query).matches;
}

function cell<T>(column: DataTableColumn<T>, record: T, index: number): ReactNode {
  if (column.render) return column.render(record, index);
  const value = getValueAtPath(record, column.accessor);
  return value == null || value === '' ? null : String(value as string | number);
}

interface Paging {
  page?: number;
  onPageChange?: (page: number) => void;
  totalRecords?: number;
  recordsPerPage?: number;
  paginationText?: (c: { from: number; to: number; totalRecords: number }) => ReactNode;
}

/**
 * Rows as cards: the first column is the heading, the first right-aligned
 * column (usually an amount) sits beside it, and the other columns follow as
 * label and value. Columns without a title (row actions) end the top line.
 */
function PhoneCards<T>(props: DataTableProps<T>) {
  const {
    columns = [],
    records = [],
    fetching,
    idAccessor = 'id',
    onRowClick,
    rowStyle,
    rowExpansion,
    noRecordsText,
    withTableBorder,
    page,
    onPageChange,
    totalRecords,
    recordsPerPage,
    paginationText,
  } = props as DataTableProps<T> & Paging;
  const theme = useMantineTheme();
  const [open, setOpen] = useState<Set<unknown>>(new Set());

  const shown = columns.filter((column) => visible(column, theme));
  const [head, ...rest] = shown;
  const aside = rest.find((c) => c.textAlign === 'right');
  const actions = rest.filter((c) => c.title === '');
  const fields = rest.filter((c) => c !== aside && !actions.includes(c));

  const boxClass = `${classes.list} ${withTableBorder ? classes.bordered : ''}`;
  if (fetching && records.length === 0) {
    return (
      <div className={boxClass}>
        <TableSkeleton rows={5} />
      </div>
    );
  }
  if (records.length === 0) {
    return (
      <div className={boxClass}>
        <Text c="dimmed" size="sm" ta="center" py="xl">
          {noRecordsText ?? 'No records'}
        </Text>
      </div>
    );
  }

  const pages =
    page !== undefined && recordsPerPage && totalRecords
      ? Math.ceil(totalRecords / recordsPerPage)
      : 0;
  const from = pages ? (page! - 1) * recordsPerPage! + 1 : 0;
  const to = pages ? Math.min(page! * recordsPerPage!, totalRecords!) : 0;

  return (
    <div className={boxClass}>
      {records.map((record, index) => {
        const id = getRecordId(record, idAccessor);
        const expanded = open.has(id);
        const clickable = !!onRowClick || !!rowExpansion;
        const style = rowStyle?.(record, index);
        const activate = (event: React.MouseEvent | React.KeyboardEvent) => {
          // Taps inside the opened details (e.g. a purchase's lines) stay there.
          if ((event.target as HTMLElement).closest('[data-expansion]')) return;
          if (onRowClick) onRowClick({ record, index, event: event as React.MouseEvent });
          else if (rowExpansion) {
            setOpen((prev) => {
              const next = new Set(prev);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            });
          }
        };
        const values = fields
          .map((column) => ({ column, value: cell(column, record, index) }))
          .filter(
            ({ value }) => value !== null && value !== undefined && value !== false && value !== '',
          );
        return (
          <div
            key={String(id)}
            className={classes.item}
            data-clickable={clickable || undefined}
            style={
              typeof style === 'object' && !Array.isArray(style)
                ? (style as CSSProperties)
                : undefined
            }
            {...(clickable && {
              role: 'button',
              tabIndex: 0,
              'aria-expanded': rowExpansion ? expanded : undefined,
              onClick: activate,
              onKeyDown: (event: React.KeyboardEvent) => {
                if (event.target !== event.currentTarget) return;
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  activate(event);
                }
              },
            })}
          >
            <div className={classes.head}>
              <div className={classes.title}>{head && cell(head, record, index)}</div>
              {aside && <div className={classes.aside}>{cell(aside, record, index)}</div>}
              {actions.map((column) => (
                <div key={String(column.accessor)} className={classes.actions}>
                  {cell(column, record, index)}
                </div>
              ))}
            </div>
            {values.length > 0 && (
              <dl className={classes.fields}>
                {values.map(({ column, value }) => (
                  <div key={String(column.accessor)} className={classes.field}>
                    <dt>{column.title ?? humanize(String(column.accessor))}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
            {rowExpansion && expanded && (
              <div className={classes.expansion} data-expansion>
                {rowExpansion.content({ record, index, collapse: () => setOpen(new Set()) })}
              </div>
            )}
          </div>
        );
      })}
      {pages > 1 && onPageChange && (
        <div className={classes.pager}>
          <Text size="xs" c="dimmed">
            {paginationText
              ? paginationText({ from, to, totalRecords: totalRecords ?? 0 })
              : `${from} - ${to} / ${totalRecords}`}
          </Text>
          <Pagination
            size="sm"
            total={pages}
            value={page}
            onChange={onPageChange}
            siblings={0}
            boundaries={1}
          />
        </div>
      )}
    </div>
  );
}
