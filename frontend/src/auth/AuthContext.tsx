import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo } from 'react';

import { api, onUnauthenticated, unwrap } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { Me } from '@/api/types';
import type { PermName } from '@/lib/permissions';

interface AuthState {
  user: Me | null;
  loading: boolean;
  can: (perm: PermName) => boolean;
  canAny: (...perms: PermName[]) => boolean;
  setUser: (user: Me) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);
export const ME_KEY = ['auth', 'me'] as const;

async function fetchMe(): Promise<Me | null> {
  try {
    return await unwrap(api.GET('/api/v1/auth/me/'));
  } catch (error) {
    if (error instanceof ApiError && (error.status === 403 || error.status === 401)) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const { data, isPending } = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 60_000 });
  const user = data ?? null;

  useEffect(
    () =>
      onUnauthenticated(() => {
        // Session expired: same clean-up as signing out, so the next person to
        // sign in never sees the previous user's data.
        client.setQueryData(ME_KEY, null);
        client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
      }),
    [client],
  );

  const setUser = useCallback((me: Me) => client.setQueryData(ME_KEY, me), [client]);

  const logout = useCallback(async () => {
    try {
      await unwrap(api.POST('/api/v1/auth/logout/'));
    } catch {
      // Offline or the session already expired: sign out on this device anyway.
    }
    // Show the login screen first, so open pages unmount instead of refetching
    // the last user's data, then drop everything that user loaded. (Clearing the
    // whole cache would also detach the signed-in query from this provider and
    // leave the old screens up.)
    await client.cancelQueries();
    client.setQueryData(ME_KEY, null);
    client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
  }, [client]);

  const value = useMemo<AuthState>(() => {
    const held = new Set(user?.permissions ?? []);
    return {
      user,
      loading: isPending,
      can: (perm) => held.has(perm),
      canAny: (...perms) => perms.some((p) => held.has(p)),
      setUser,
      logout,
    };
  }, [user, isPending, setUser, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
