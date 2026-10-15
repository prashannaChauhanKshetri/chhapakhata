/**
 * API errors follow drf-standardized-errors:
 * `{ type, errors: [{ code, detail, attr }] }`. `attr` is a dotted field path
 * such as `items.0.width`, which matches Mantine form paths directly.
 */
export interface ApiErrorItem {
  code: string;
  detail: string;
  attr: string | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: Record<string, string>;
  readonly items: ApiErrorItem[];

  constructor(status: number, items: ApiErrorItem[], fallback?: string) {
    const general = items.filter(
      (i) => !i.attr || i.attr === 'non_field_errors' || i.attr === 'detail',
    );
    const message =
      general[0]?.detail ?? items[0]?.detail ?? fallback ?? ApiError.statusMessage(status);
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.items = items;
    this.code = items[0]?.code ?? 'error';
    this.fieldErrors = Object.fromEntries(
      items
        .filter((i) => i.attr && i.attr !== 'non_field_errors' && i.attr !== 'detail')
        .map((i) => [i.attr as string, i.detail]),
    );
  }

  get isUnauthenticated(): boolean {
    return this.status === 401 || this.code === 'not_authenticated';
  }

  get isForbidden(): boolean {
    return this.status === 403 && !this.isUnauthenticated;
  }

  /** Message for a toast: the general error, or the first field error. */
  get summary(): string {
    return this.message;
  }

  static statusMessage(status: number): string {
    if (status === 0) return 'Cannot reach the server. Check that the shop computer is on.';
    if (status === 403) return 'You do not have permission to do this.';
    if (status === 404) return 'This record no longer exists.';
    if (status === 429) return 'Too many attempts. Please wait a moment and try again.';
    if (status >= 500) return 'The server had a problem. Try again; if it repeats, tell the owner.';
    return 'Something went wrong. Please try again.';
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let items: ApiErrorItem[] = [];
    try {
      const body = (await response.clone().json()) as { errors?: ApiErrorItem[]; detail?: string };
      if (Array.isArray(body.errors)) items = body.errors;
      else if (body.detail) items = [{ code: 'error', detail: body.detail, attr: null }];
    } catch {
      // Non-JSON body (e.g. a proxy error page): fall back to the status message.
    }
    return new ApiError(response.status, items);
  }

  static fromBody(status: number, body: unknown): ApiError {
    const errors = (body as { errors?: ApiErrorItem[] } | undefined)?.errors;
    return new ApiError(status, Array.isArray(errors) ? errors : []);
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.summary;
  if (error instanceof Error) return error.message;
  return 'Something went wrong. Please try again.';
}
