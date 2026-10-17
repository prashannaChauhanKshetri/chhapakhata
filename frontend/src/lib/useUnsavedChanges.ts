import { modals } from '@mantine/modals';
import { useEffect, useRef } from 'react';
import { useBlocker } from 'react-router';

/**
 * Ask before leaving a form with unsaved changes: in-app links, the back
 * button, closing the tab or reloading. `isDirty` is read at the moment the
 * user tries to leave, so it always reflects the latest input.
 */
export function useUnsavedChanges(isDirty: () => boolean, message: string): void {
  const check = useRef(isDirty);
  useEffect(() => {
    check.current = isDirty;
  });

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      check.current() && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    let settled = false;
    modals.openConfirmModal({
      title: 'Leave without saving?',
      children: message,
      labels: { confirm: 'Leave and discard', cancel: 'Keep editing' },
      confirmProps: { color: 'red' },
      onConfirm: () => {
        settled = true;
        blocker.proceed();
      },
      onClose: () => {
        if (!settled) blocker.reset();
      },
    });
  }, [blocker, message]);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!check.current()) return;
      event.preventDefault();
      event.returnValue = ''; // older browsers need this to show their own prompt
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);
}
