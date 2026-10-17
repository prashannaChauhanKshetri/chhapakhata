import { notifications } from '@mantine/notifications';

import { ApiError, errorMessage } from '@/api/errors';

const RELOADED_KEY = 'ck-reloaded-for-update';

/**
 * Safety nets for errors no screen handled:
 * - a rejected promise from a button or background task becomes a toast
 *   instead of failing silently;
 * - after an update, pages from the old version can no longer be loaded, so
 *   reload once to pick up the new version.
 */
export function installGlobalErrorHandlers(): void {
  window.addEventListener('unhandledrejection', (event) => {
    const error: unknown = event.reason;
    if (error instanceof DOMException && error.name === 'AbortError') return;
    if (error instanceof ApiError && error.isUnauthenticated) return; // login screen takes over
    notifications.show({
      color: 'red',
      title: 'Something went wrong',
      message: errorMessage(error),
    });
  });

  window.addEventListener('vite:preloadError', (event) => {
    let reloaded = false;
    try {
      reloaded = sessionStorage.getItem(RELOADED_KEY) === '1';
      sessionStorage.setItem(RELOADED_KEY, '1');
    } catch {
      // Storage blocked: fall through and let the error screen offer a reload.
    }
    if (!reloaded) {
      event.preventDefault();
      window.location.reload();
    }
  });
  window.addEventListener('load', () => {
    window.setTimeout(() => {
      try {
        sessionStorage.removeItem(RELOADED_KEY);
      } catch {
        // ignore
      }
    }, 10_000);
  });
}

/** True for "this part of the app could not be downloaded" (usually: a new version). */
export function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return /dynamically imported module|Importing a module script failed|error loading dynamically/i.test(
    message,
  );
}
