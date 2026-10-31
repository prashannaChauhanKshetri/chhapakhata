import { DataTable as BaseDataTable, type DataTableProps } from 'mantine-datatable';

import { TableSkeleton } from './Skeletons';

/** The app's data table: skeleton rows, not a spinner, while records load. */
export function DataTable<T>(props: DataTableProps<T>) {
  // The props type is a union that forbids customLoader alongside spinner
  // options; the app never sets those, so replacing the loader is safe.
  const withSkeleton = {
    ...props,
    customLoader: <TableSkeleton />,
    loaderBackgroundBlur: 0,
  } as DataTableProps<T>;
  return <BaseDataTable<T> {...withSkeleton} />;
}
