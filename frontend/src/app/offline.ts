/**
 * Online / offline behaviour.
 *
 * "Online" means the shop computer answers, not just that the device has
 * Wi-Fi: a phone can be on the network while the server is switched off.
 * TanStack Query's online manager follows that, so when the server is away
 * queries pause and pages keep showing the last data they loaded.
 *
 * That data is also saved on the device (for 24 hours, cleared on sign-out),
 * so the app opens and shows recent orders, jobs and balances without the
 * server. Saving changes needs the server, because order, invoice and receipt
 * numbers and stock levels are allocated there; while offline, writes are
 * refused with a clear message instead of failing halfway.
 */
import { onlineManager } from '@tanstack/react-query';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import type { PersistQueryClientOptions } from '@tanstack/react-query-persist-client';
import { useSyncExternalStore } from 'react';

const HEALTH_URL = '/api/v1/health/';
const CHECK_EVERY_MS = 15_000;
const CHECK_TIMEOUT_MS = 5_000;
const CACHE_KEY = 'ck-saved-data';
const LAST_ONLINE_KEY = 'ck-last-online';

export type Connection = 'online' | 'no-network' | 'server-unreachable';

let connection: Connection = 'online';
let lastOnlineAt: number | null = readLastOnline();
const listeners = new Set<() => void>();
let runCheck: (() => void) | null = null;

function readLastOnline(): number | null {
  try {
    const value = Number(localStorage.getItem(LAST_ONLINE_KEY));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

function setConnection(next: Connection) {
  if (next === 'online') {
    lastOnlineAt = Date.now();
    try {
      localStorage.setItem(LAST_ONLINE_KEY, String(lastOnlineAt));
    } catch {
      // Storage blocked (private mode): the banner just won't show the time.
    }
  }
  if (next !== connection) {
    connection = next;
    listeners.forEach((l) => l());
  }
}

async function serverAnswers(): Promise<boolean> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CHECK_TIMEOUT_MS);
  try {
    const response = await fetch(HEALTH_URL, {
      cache: 'no-store',
      credentials: 'same-origin',
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}

/** Start watching the connection. Called once at start-up. */
export function startConnectionWatch(): void {
  onlineManager.setEventListener((setOnline) => {
    let checking = false;
    const check = async () => {
      if (checking) return;
      checking = true;
      try {
        if (!navigator.onLine) {
          setConnection('no-network');
        } else {
          setConnection((await serverAnswers()) ? 'online' : 'server-unreachable');
        }
        setOnline(connection === 'online');
      } finally {
        checking = false;
      }
    };
    runCheck = () => void check();
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check();
    };
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void check();
    }, CHECK_EVERY_MS);
    window.addEventListener('online', runCheck);
    window.addEventListener('offline', runCheck);
    document.addEventListener('visibilitychange', onVisible);
    void check();
    return () => {
      window.clearInterval(timer);
      if (runCheck) {
        window.removeEventListener('online', runCheck);
        window.removeEventListener('offline', runCheck);
      }
      document.removeEventListener('visibilitychange', onVisible);
      runCheck = null;
    };
  });
}

/** Re-check now, e.g. after a request could not reach the server. */
export function checkConnectionSoon(): void {
  runCheck?.();
}

export function isOnline(): boolean {
  return connection === 'online';
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The connection state and when the server last answered, for banners. */
export function useConnection(): { connection: Connection; lastOnlineAt: number | null } {
  const value = useSyncExternalStore(subscribe, () => connection);
  return { connection: value, lastOnlineAt };
}

// ---------- saved data ----------

function storage(): Storage | undefined {
  try {
    const probe = '__ck_probe__';
    window.localStorage.setItem(probe, probe);
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return undefined; // private mode or storage blocked: work without saved data
  }
}

/** Queries that are not worth saving (live calculations, one-off checks). */
const NOT_SAVED = new Set(['price-preview', 'utils']);

export const persistOptions: Omit<PersistQueryClientOptions, 'queryClient'> = {
  persister: createSyncStoragePersister({
    storage: storage(),
    key: CACHE_KEY,
    throttleTime: 2_000,
  }),
  maxAge: 24 * 60 * 60 * 1000,
  // Bump when the shape of saved data changes, so old copies are discarded.
  buster: 'v1',
  dehydrateOptions: {
    shouldDehydrateQuery: (query) =>
      query.state.status === 'success' && !NOT_SAVED.has(String(query.queryKey[0])),
  },
};

/** Forget the saved copy (sign-out, session expiry). */
export function clearSavedData(): void {
  try {
    window.localStorage.removeItem(CACHE_KEY);
  } catch {
    // nothing saved
  }
}
