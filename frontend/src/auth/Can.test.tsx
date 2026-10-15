import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { theme } from '@/app/theme';
import { Money } from '@/components/Money';

const held = new Set<string>(['orders.view']);
vi.mock('./AuthContext', () => ({
  useAuth: () => ({
    can: (p: string) => held.has(p),
    canAny: (...p: string[]) => p.some((x) => held.has(x)),
  }),
}));

const { Can } = await import('./Can');
const { RequirePerm } = await import('./RequirePerm');

const wrap = (node: ReactNode) =>
  render(
    <MantineProvider theme={theme}>
      <MemoryRouter>{node}</MemoryRouter>
    </MantineProvider>,
  );

describe('permission gates', () => {
  it('shows children only with the permission', () => {
    wrap(
      <>
        <Can perm="orders.view">visible</Can>
        <Can perm="users.manage" fallback={<span>no access</span>}>
          hidden
        </Can>
      </>,
    );
    expect(screen.getByText('visible')).toBeInTheDocument();
    expect(screen.queryByText('hidden')).not.toBeInTheDocument();
    expect(screen.getByText('no access')).toBeInTheDocument();
  });

  it('route guard explains missing access', () => {
    wrap(<RequirePerm perm="settings.manage">secret</RequirePerm>);
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
    expect(screen.getByText('You do not have access to this page')).toBeInTheDocument();
  });
});

describe('Money', () => {
  it('renders rupees with lakh grouping', () => {
    wrap(<Money value="125000" />);
    expect(screen.getByText('Rs. 1,25,000.00')).toBeInTheDocument();
  });
});
