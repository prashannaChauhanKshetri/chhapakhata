import { Anchor, Button, Group, Text, UnstyledButton } from '@mantine/core';
import type { ReactNode } from 'react';

import { goTo } from '@/app/publicNav';
import { Logo } from '@/components/Logo';

import classes from './HomePage.module.css';

/** The top bar of the public pages. `links` are in-page links (the home page's sections). */
export function PublicNav({ links }: { links?: { href: string; label: string }[] }) {
  return (
    <header className={classes.nav}>
      <div className={`${classes.wrap} ${classes.navInner}`}>
        <UnstyledButton onClick={() => goTo('/')} aria-label="ChhapaKhata home">
          <Logo size={34} />
        </UnstyledButton>
        <Group gap="lg" wrap="nowrap">
          {links && (
            <Group gap="lg" visibleFrom="sm">
              {links.map((l) => (
                <Anchor key={l.href} href={l.href} c="dimmed" size="sm">
                  {l.label}
                </Anchor>
              ))}
            </Group>
          )}
          <Button onClick={() => goTo('/login')} variant="default">
            Sign in
          </Button>
        </Group>
      </div>
    </header>
  );
}

function FooterLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Anchor component="button" size="sm" c="dimmed" onClick={() => goTo(to)}>
      {children}
    </Anchor>
  );
}

export function PublicFooter() {
  return (
    <footer className={classes.footer}>
      <div className={`${classes.wrap} ${classes.footerInner}`}>
        <Logo size={24} />
        <Text size="sm" c="dimmed">
          छापा means print, खाता the account book. Made in Nepal.
        </Text>
        <Group gap="md">
          <FooterLink to="/terms">Terms</FooterLink>
          <FooterLink to="/privacy">Privacy</FooterLink>
          <FooterLink to="/login">Staff sign in</FooterLink>
        </Group>
      </div>
    </footer>
  );
}
