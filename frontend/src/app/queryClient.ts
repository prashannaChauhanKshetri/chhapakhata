import { notifications } from '@mantine/notifications';
import { QueryCache, QueryClient } from '@tanstack/react-query';

import { ApiError, errorMessage } from '@/api/errors';

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    // A page that already shows data refreshes it in the background. If that
    // refresh fails, say so, otherwise old figures would look current.
    // (A first load that fails shows its own error box instead.)
    onError: (error, query) => {
      if (query.state.data === undefined) return;
      if (error instanceof ApiError && (error.isUnauthenticated || error.status === 0)) return;
      notifications.show({
        id: 'refresh-failed',
        color: 'amber',
        title: 'Could not refresh',
        message: `${errorMessage(error)} What you see may be out of date.`,
      });
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => {
        // Never retry permission or validation problems; retry network blips twice.
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 2;
      },
    },
    mutations: { retry: false },
  },
});
