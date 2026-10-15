import { MantineProvider } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { Notifications } from '@mantine/notifications';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';

import { AuthProvider, useAuth } from '@/auth/AuthContext';
import { LoginPage } from '@/auth/LoginPage';
import { PageLoader } from '@/components/PageLoader';

import { AppErrorBoundary } from './AppErrorBoundary';
import { queryClient } from './queryClient';
import { router } from './router';
import { theme } from './theme';

function Gate() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <LoginPage />;
  return <RouterProvider router={router} />;
}

export function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="light" forceColorScheme="light">
      <DatesProvider settings={{ firstDayOfWeek: 0, consistentWeeks: true }}>
        <QueryClientProvider client={queryClient}>
          <Notifications position="top-right" autoClose={4000} />
          <AppErrorBoundary>
            <AuthProvider>
              <Gate />
            </AuthProvider>
          </AppErrorBoundary>
        </QueryClientProvider>
      </DatesProvider>
    </MantineProvider>
  );
}
