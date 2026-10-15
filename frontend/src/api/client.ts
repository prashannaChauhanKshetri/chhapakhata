/**
 * Typed API client. Paths and payloads come from the backend's OpenAPI schema
 * (`npm run api:types`), so a backend change that breaks the contract fails
 * the TypeScript build instead of failing at the shop counter.
 *
 * Auth is the Django session cookie (same origin). Unsafe requests carry the
 * CSRF token from the `csrftoken` cookie.
 */
import createClient, { type Middleware } from 'openapi-fetch';

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

const csrfAndErrors: Middleware = {
  async onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      request.headers.set('X-CSRFToken', await ensureCsrfCookie());
    }
    return request;
  },
  async onResponse({ response, request }) {
    if (response.status === 403 && !request.url.includes('/auth/')) {
      const error = await ApiError.fromResponse(response);
      if (error.isUnauthenticated) authListeners.forEach((l) => l(error));
    }
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: '', credentials: 'same-origin' });
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
  } catch {
    throw new ApiError(0, []);
  }
  if (!result.response.ok) {
    throw ApiError.fromBody(result.response.status, result.error);
  }
  return result.data as T;
}
