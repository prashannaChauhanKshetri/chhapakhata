/**
 * Installable app ("Add to Home Screen") and updates.
 *
 * - The service worker stores the app itself on the device so it opens
 *   without the server (registered only in production builds).
 * - When a new version is deployed, staff see "New version ready" and choose
 *   when to reload, so nobody loses a half-filled order.
 * - Chrome/Edge/Android offer a one-tap install; iPhone and iPad need Safari's
 *   Share → Add to Home Screen, which we explain.
 */
import { Button, Group, List, Text } from '@mantine/core';
import { modals } from '@mantine/modals';
import { notifications } from '@mantine/notifications';
import { useEffect, useState } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let deferredPrompt: InstallPromptEvent | null = null;
const installListeners = new Set<() => void>();

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); // show our own "Install app" instead of the browser's mini bar
    deferredPrompt = event as InstallPromptEvent;
    installListeners.forEach((l) => l());
  });
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    installListeners.forEach((l) => l());
  });
}

export function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function isIos(): boolean {
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  );
}

/** How (and whether) this device can install the app. */
export function useInstall(): { canInstall: boolean; install: () => void } {
  const [, force] = useState(0);
  useEffect(() => {
    const update = () => force((n) => n + 1);
    installListeners.add(update);
    return () => {
      installListeners.delete(update);
    };
  }, []);
  if (isStandalone()) return { canInstall: false, install: () => undefined };
  if (deferredPrompt) {
    const prompt = deferredPrompt;
    return {
      canInstall: true,
      install: () => {
        void prompt.prompt();
        void prompt.userChoice.then(() => {
          deferredPrompt = null;
          installListeners.forEach((l) => l());
        });
      },
    };
  }
  if (isIos()) {
    return {
      canInstall: true,
      install: () =>
        modals.open({
          title: 'Add ChhapaKhata to the Home Screen',
          children: (
            <List type="ordered" spacing="xs" size="sm">
              <List.Item>Open this page in Safari.</List.Item>
              <List.Item>Tap the Share button (the square with an arrow).</List.Item>
              <List.Item>Choose “Add to Home Screen”, then “Add”.</List.Item>
            </List>
          ),
        }),
    };
  }
  return { canInstall: false, install: () => undefined };
}

/** Registers the service worker and offers updates. Renders nothing. */
export function PwaManager() {
  const {
    needRefresh: [needRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisterError: () => {
      // Plain HTTP on a phone (not localhost) cannot register a service worker;
      // the app still works online, it just can't be installed or open offline.
    },
  });

  useEffect(() => {
    if (!offlineReady) return;
    notifications.show({
      color: 'green',
      title: 'Ready to work offline',
      message: 'ChhapaKhata will now open even when the shop computer is off.',
    });
    setOfflineReady(false);
  }, [offlineReady, setOfflineReady]);

  useEffect(() => {
    if (!needRefresh) return;
    notifications.show({
      id: 'app-update',
      color: 'slate',
      autoClose: false,
      withCloseButton: true,
      title: 'New version ready',
      message: (
        <Group justify="space-between" gap="sm" mt={4}>
          <Text size="sm">Save what you are doing, then reload.</Text>
          <Button size="xs" onClick={() => void updateServiceWorker(true)}>
            Reload now
          </Button>
        </Group>
      ),
    });
  }, [needRefresh, updateServiceWorker]);

  return null;
}
