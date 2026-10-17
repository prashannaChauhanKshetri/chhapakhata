import { Button, Center, MantineProvider, Stack, Text, Title } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { useMediaQuery } from '@mantine/hooks';
import { Notifications } from '@mantine/notifications';
import { IconWifiOff } from '@tabler/icons-react';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { useEffect, useRef } from 'react';
import { RouterProvider } from 'react-router';

import { AuthProvider, useAuth } from '@/auth/AuthContext';
import { LoginPage } from '@/auth/LoginPage';
import { PageLoader } from '@/components/PageLoader';

import { AppErrorBoundary } from './AppErrorBoundary';
import { checkConnectionSoon, persistOptions, useConnection } from './offline';
import { PwaManager } from './pwa';
import { queryClient } from './queryClient';
import { router } from './router';
import { theme } from './theme';

/** Toasts: top-right on desktop; full width at the top on phones so no text is cut off. */
function AppNotifications() {
  const isPhone = useMediaQuery('(max-width: 36em)');
  return (
    <Notifications
      position={isPhone ? 'top-center' : 'top-right'}
      containerWidth={isPhone ? 'calc(100vw - 16px)' : 440}
      autoClose={4000}
    />
  );
}

/** First start with no server and nothing saved on this device yet. */
function NoServerYet() {
  return (
    <Center mih="100vh" p="lg" bg="var(--ck-bg)">
      <Stack align="center" gap="sm" maw={420} ta="center">
        <IconWifiOff size={40} stroke={1.5} color="var(--mantine-color-slate-6)" />
        <Title order={2}>Cannot reach the shop computer</Title>
        <Text c="dimmed">
          Check that this device is on the shop Wi-Fi and the shop computer is switched on. Once you
          have signed in here, recent data stays available even when the connection drops.
        </Text>
        <Button mt="sm" onClick={checkConnectionSoon}>
          Try again
        </Button>
      </Stack>
    </Center>
  );
}

function Gate() {
  const { user, loading } = useAuth();
  const { connection } = useConnection();
  const wasSignedIn = useRef(false);

  // After signing out (or a session expiring), start the next person on the
  // dashboard rather than on the last user's page, which they may not be allowed to see.
  useEffect(() => {
    if (user) wasSignedIn.current = true;
    else if (wasSignedIn.current) {
      wasSignedIn.current = false;
      void router.navigate('/', { replace: true });
    }
  }, [user]);

  if (loading) return connection === 'online' ? <PageLoader /> : <NoServerYet />;
  if (!user) return <LoginPage />;
  return <RouterProvider router={router} />;
}

export function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="light" forceColorScheme="light">
      <DatesProvider settings={{ firstDayOfWeek: 0, consistentWeeks: true }}>
        <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
          <AppNotifications />
          <PwaManager />
          <AppErrorBoundary>
            <AuthProvider>
              <Gate />
            </AuthProvider>
          </AppErrorBoundary>
        </PersistQueryClientProvider>
      </DatesProvider>
    </MantineProvider>
  );
}
