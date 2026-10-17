import { Group, Kbd, Stack, Table, Text } from '@mantine/core';
import { modals } from '@mantine/modals';
import { useEffect } from 'react';
import { useNavigate } from 'react-router';

import { useAuth } from '@/auth/AuthContext';
import { Perm } from '@/lib/permissions';

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);
const MOD = isMac ? '⌘' : 'Ctrl';

const SHORTCUTS: { keys: string[]; action: string }[] = [
  { keys: ['/'], action: 'Jump to the search box on this page' },
  { keys: ['N'], action: 'Start a new order' },
  { keys: [MOD, 'S'], action: 'Save the order (on the order screen)' },
  { keys: ['Enter'], action: 'Add another item (in the last item of an order)' },
  { keys: ['Esc'], action: 'Close a dialog or menu' },
  { keys: ['?'], action: 'Show this list' },
];

export function openShortcuts() {
  modals.open({
    title: 'Keyboard shortcuts',
    children: (
      <Stack gap="xs">
        <Table verticalSpacing={6}>
          <Table.Tbody>
            {SHORTCUTS.map((s) => (
              <Table.Tr key={s.action}>
                <Table.Td w={120}>
                  <Group gap={4} wrap="nowrap">
                    {s.keys.map((k) => (
                      <Kbd key={k}>{k}</Kbd>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{s.action}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Text size="xs" c="dimmed">
          Single-key shortcuts work when you are not typing in a box.
        </Text>
      </Stack>
    ),
  });
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
    target.getAttribute('role') === 'combobox'
  );
}

/** App-wide shortcuts for frequent users. Ignored while typing in a field. */
export function useAppShortcuts() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const mayOrder = can(Perm.ORDERS_MANAGE);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTyping(event.target) || document.querySelector('[role="dialog"]')) return;
      if (event.key === '/') {
        const box = document.querySelector<HTMLInputElement>(
          'main input[aria-label^="Search"], main input[placeholder^="Search"], main input[type="search"]',
        );
        if (box) {
          event.preventDefault();
          box.focus();
          box.select();
        }
      } else if (event.key === 'n' || event.key === 'N') {
        if (mayOrder) {
          event.preventDefault();
          void navigate('/orders/new');
        }
      } else if (event.key === '?') {
        event.preventDefault();
        openShortcuts();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [navigate, mayOrder]);
}
