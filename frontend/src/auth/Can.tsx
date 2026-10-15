import type { ReactNode } from 'react';

import type { PermName } from '@/lib/permissions';

import { useAuth } from './AuthContext';

interface CanProps {
  /** Show children if the user holds this permission (or any of these). */
  perm: PermName | PermName[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function Can({ perm, children, fallback = null }: CanProps) {
  const { canAny } = useAuth();
  const perms = Array.isArray(perm) ? perm : [perm];
  return <>{canAny(...perms) ? children : fallback}</>;
}
