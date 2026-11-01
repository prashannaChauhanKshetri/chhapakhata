import { ensureCsrfCookie, fetchWithTimeout } from '@/api/client';
import { ApiError } from '@/api/errors';
import { FILE_TIMEOUT_MS } from '@/api/files';

/** Every spreadsheet type the server reads (it checks the contents, not the name). */
export const SHEET_TYPES = '.xlsx,.xlsm,.xltx,.xltm,.xlsb,.xls,.ods,.csv,.tsv,.txt';

/** Header text in the sheet → field it holds ("" = not used). */
export type ColumnChoices = Record<string, string>;

export interface UploadOptions {
  dryRun: boolean;
  skipErrors?: boolean;
  columns?: ColumnChoices | null;
  asOf?: string | null;
}

/** Send a sheet to an import endpoint; a dry run checks it without saving. */
export async function uploadSheet<T>(url: string, file: File, options: UploadOptions): Promise<T> {
  const body = new FormData();
  body.append('file', file);
  body.append('dry_run', String(options.dryRun));
  body.append('skip_errors', String(options.skipErrors ?? false));
  if (options.columns) body.append('columns', JSON.stringify(options.columns));
  if (options.asOf) body.append('as_of', options.asOf);
  const response = await fetchWithTimeout(
    url,
    {
      method: 'POST',
      body,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': await ensureCsrfCookie() },
    },
    FILE_TIMEOUT_MS,
  );
  if (!response.ok) throw await ApiError.fromResponse(response);
  return (await response.json()) as T;
}

/** The server's guesses (field → header) turned round, for the column fixer. */
export function choicesFrom(columns: Record<string, string>, headers: string[]): ColumnChoices {
  const byHeader: ColumnChoices = Object.fromEntries(headers.map((h) => [h, '']));
  for (const [field, header] of Object.entries(columns)) byHeader[header] = field;
  return byHeader;
}
