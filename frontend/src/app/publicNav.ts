/**
 * Moving between the pages seen before signing in (home and sign-in).
 *
 * They go through the app's router so its location stays right: after signing
 * in, the router carries on from where the visitor is (or the dashboard).
 */
import { useSyncExternalStore } from 'react';

import { router } from './router';

const subscribe = (onChange: () => void) => router.subscribe(onChange);
const pathname = () => router.state.location.pathname;

/** The current path, kept up to date while signed out too. */
export function usePathname(): string {
  return useSyncExternalStore(subscribe, pathname);
}

/** Open a page and start it at the top. */
export function goTo(path: string, options: { replace?: boolean } = {}): void {
  void router.navigate(path, { replace: options.replace }).then(() => window.scrollTo(0, 0));
}
