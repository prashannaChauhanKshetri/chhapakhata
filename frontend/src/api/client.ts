/**
 * Typed API client. Paths and payloads come from the backend's OpenAPI schema
 * (`npm run api:types`), so a backend change that breaks the contract fails
 * the TypeScript build instead of failing at the shop counter.
 *
 * Auth is the Django session cookie (same origin). Unsafe requests carry the
 * CSRF token from the `csrftoken` cookie.
 */
import createClient, { type Middleware } from 'openapi-fetch';

import { checkConnectionSoon, isOnline } from '@/app/offline';

import { ApiError } from './errors';
import type { paths } from './schema';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export function readCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

export async function ensureCsrfCookie(): Promise<string> {
  let token = readCookie('csrftoken');
  if (!token) {
    await fetch('/api/v1/auth/csrf/', { credentials: 'same-origin' });
    token = readCookie('csrftoken');
  }
  return token ?? '';
}

type Listener = (error: ApiError) => void;
const authListeners = new Set<Listener>();

/** Called when any request finds the session expired. */
export function onUnauthenticated(listener: Listener): () => void {
  authListeners.add(listener);
  return () => authListeners.delete(listener);
}

/** Tell the app the session has ended (any request may discover this). */
export function reportIfUnauthenticated(error: ApiError, url: string): void {
  if (error.isUnauthenticated && !url.includes('/auth/')) authListeners.forEach((l) => l(error));
}

/** Requests that take longer than this are abandoned, so the screen never hangs. */
export const REQUEST_TIMEOUT_MS = 30_000;

/**
 * `fetch` with a time limit; a timeout surfaces like any other network failure.
 * Written without `AbortSignal.any`/`timeout` so older phones are supported.
 */
export function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const method = (init.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
  const url = input instanceof Request ? input.url : String(input);
  if (!SAFE_METHODS.has(method) && !isOnline() && !url.includes('/auth/logout')) {
    // Refuse up front rather than half-saving: numbers and stock live on the server.
    return Promise.reject(new ApiError(0, [], ApiError.OFFLINE_WRITE_MESSAGE));
  }
  const controller = new AbortController();
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const outer = init.signal ?? (input instanceof Request ? input.signal : undefined);
  const forward = () => controller.abort();
  if (outer?.aborted) controller.abort();
  else outer?.addEventListener('abort', forward, { once: true });
  return fetch(input, { ...init, signal: controller.signal })
    .catch((error: unknown) => {
      if (!controller.signal.aborted || timedOut) checkConnectionSoon();
      if (timedOut) throw new ApiError(0, [], ApiError.TIMEOUT_MESSAGE);
      throw error;
    })
    .finally(() => {
      window.clearTimeout(timer);
      outer?.removeEventListener('abort', forward);
    });
}

const csrfAndErrors: Middleware = {
  async onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      request.headers.set('X-CSRFToken', await ensureCsrfCookie());
    }
    return request;
  },
  async onResponse({ response, request }) {
    if (response.status === 403 || response.status === 401) {
      reportIfUnauthenticated(await ApiError.fromResponse(response), request.url);
    }
    return response;
  },
};

export const api = createClient<paths>({
  baseUrl: '',
  credentials: 'same-origin',
  fetch: (request: Request) => fetchWithTimeout(request),
});
api.use(csrfAndErrors);

/**
 * Unwrap an openapi-fetch result: return data or throw an `ApiError`.
 *
 *     const order = await unwrap(api.GET('/api/v1/orders/{id}/', { params: { path: { id } } }));
 */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await promise;
  } catch (error) {
    throw error instanceof ApiError ? error : new ApiError(0, []);
  }
  if (!result.response.ok) {
    throw ApiError.fromBody(result.response.status, result.error);
  }
  return result.data as T;
}
