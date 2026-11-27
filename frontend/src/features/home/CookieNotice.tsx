import { Anchor, Button, Group, Paper, Text } from '@mantine/core';
import { IconCookie } from '@tabler/icons-react';
import { useState } from 'react';

import { goTo } from '@/app/publicNav';

import classes from './HomePage.module.css';

const KEY = 'ck-cookie-note-seen';

function seen(): boolean {
  try {
    return window.localStorage.getItem(KEY) === '1';
  } catch {
    return false; // storage blocked: show it; OK hides it for this visit
  }
}

/**
 * A note, not a consent banner: ChhapaKhata sets only the cookies it needs to sign
 * people in, with no tracking, so there is nothing to accept or refuse.
 */
export function CookieNotice() {
  const [open, setOpen] = useState(() => !seen());
  if (!open) return null;
  const close = () => {
    try {
      window.localStorage.setItem(KEY, '1');
    } catch {
      // not remembered; it closes anyway
    }
    setOpen(false);
  };
  return (
    <Paper className={classes.cookie} shadow="lg" withBorder role="region" aria-label="Cookies">
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <IconCookie size={22} stroke={1.6} className={classes.cookieIcon} />
        <div>
          <Text size="sm">Only the cookies needed to keep you signed in. No tracking, no ads.</Text>
          <Group gap="sm" mt={10}>
            <Button size="xs" onClick={close}>
              OK
            </Button>
            <Anchor component="button" size="sm" onClick={() => goTo('/privacy')}>
              Privacy policy
            </Anchor>
          </Group>
        </div>
      </Group>
    </Paper>
  );
}
