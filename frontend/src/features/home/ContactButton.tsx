import { Button, type ButtonProps, Menu } from '@mantine/core';
import { useClipboard } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconBrandGmail, IconCopy, IconMail } from '@tabler/icons-react';
import type { ReactNode } from 'react';

export const EMAIL = 'prashannachauhankshetri@gmail.com';
const SUBJECT = 'ChhapaKhata for my shop';
const MAILTO = `mailto:${EMAIL}?subject=${encodeURIComponent(SUBJECT)}`;
const GMAIL = `https://mail.google.com/mail/?view=cm&fs=1&to=${EMAIL}&su=${encodeURIComponent(SUBJECT)}`;

/**
 * A button that offers three ways to write: a plain mailto link does nothing on
 * a computer with no email app set up (most people use Gmail in the browser).
 */
export function ContactButton({ children, ...props }: ButtonProps & { children: ReactNode }) {
  const clipboard = useClipboard();
  const copy = () => {
    clipboard.copy(EMAIL);
    notifications.show({ color: 'green', message: `Copied ${EMAIL}` });
  };
  return (
    <Menu position="bottom" shadow="md" width={240} withinPortal>
      <Menu.Target>
        <Button {...props}>{children}</Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item
          component="a"
          href={GMAIL}
          target="_blank"
          rel="noopener noreferrer"
          leftSection={<IconBrandGmail size={16} />}
        >
          Write in Gmail
        </Menu.Item>
        <Menu.Item component="a" href={MAILTO} leftSection={<IconMail size={16} />}>
          Use my email app
        </Menu.Item>
        <Menu.Item onClick={copy} leftSection={<IconCopy size={16} />}>
          Copy email address
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
