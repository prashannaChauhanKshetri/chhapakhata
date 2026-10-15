import { useDebouncedValue } from '@mantine/hooks';
import type { DataTableSortStatus } from 'mantine-datatable';
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

export const PAGE_SIZE = 25;

/**
 * List state (page, search, sort, filters) kept in the URL, so the back
 * button and shared links restore exactly what was on screen.
 */
export function useListState<F extends string>(
  filterKeys: readonly F[] = [],
  defaultSort?: string,
) {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') ?? '1') || 1;
  const search = params.get('q') ?? '';
  const ordering = params.get('ordering') ?? defaultSort ?? '';
  const [debouncedSearch] = useDebouncedValue(search, 300);

  const filters = Object.fromEntries(filterKeys.map((k) => [k, params.get(k) ?? ''])) as Record<
    F,
    string
  >;

  const update = useCallback(
    (changes: Record<string, string | number | null | undefined>, resetPage = true) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(changes)) {
            if (value === null || value === undefined || value === '') next.delete(key);
            else next.set(key, String(value));
          }
          if (resetPage && !('page' in changes)) next.delete('page');
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const sortStatus: DataTableSortStatus<Record<string, unknown>> | undefined = ordering
    ? {
        columnAccessor: ordering.replace(/^-/, ''),
        direction: ordering.startsWith('-') ? 'desc' : 'asc',
      }
    : undefined;

  return {
    page,
    search,
    debouncedSearch,
    ordering,
    filters,
    sortStatus,
    setPage: (p: number) => update({ page: p === 1 ? null : p }, false),
    setSearch: (q: string) => update({ q }),
    setFilter: (key: F, value: string | null) => update({ [key]: value }),
    setSort: (status: DataTableSortStatus<Record<string, unknown>>) =>
      update({ ordering: `${status.direction === 'desc' ? '-' : ''}${status.columnAccessor}` }),
    /** Query parameters for the API call. */
    query: {
      page,
      page_size: PAGE_SIZE,
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
      ...(ordering ? { ordering } : {}),
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
    } as Record<string, string | number>,
  };
}
