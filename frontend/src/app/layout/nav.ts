import {
  IconBook2,
  IconBuildingWarehouse,
  IconChartBar,
  IconChartDots3,
  IconClipboardList,
  IconFileInvoice,
  IconLayoutDashboard,
  IconLayoutKanban,
  IconReceipt2,
  IconSettings,
  IconTruckDelivery,
  IconUsers,
  type Icon,
} from '@tabler/icons-react';

import { Perm, type PermName } from '@/lib/permissions';

export interface NavItem {
  label: string;
  to: string;
  icon: Icon;
  /** Visible when the user has any of these. */
  perms: PermName[];
  /** Match only the exact path (for "/"). */
  end?: boolean;
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    items: [{ label: 'Dashboard', to: '/', icon: IconLayoutDashboard, perms: [], end: true }],
  },
  {
    label: 'Work',
    items: [
      { label: 'Orders', to: '/orders', icon: IconClipboardList, perms: [Perm.ORDERS_VIEW] },
      {
        label: 'Production',
        to: '/production',
        icon: IconLayoutKanban,
        perms: [Perm.PRODUCTION_VIEW],
      },
      { label: 'Customers', to: '/customers', icon: IconUsers, perms: [Perm.CUSTOMERS_VIEW] },
    ],
  },
  {
    label: 'Money',
    items: [
      { label: 'Invoices', to: '/invoices', icon: IconFileInvoice, perms: [Perm.INVOICES_VIEW] },
      { label: 'Payments', to: '/payments', icon: IconReceipt2, perms: [Perm.PAYMENTS_VIEW] },
      { label: 'Ledger', to: '/ledger', icon: IconBook2, perms: [Perm.LEDGER_VIEW] },
    ],
  },
  {
    label: 'Stock',
    items: [
      {
        label: 'Inventory',
        to: '/inventory',
        icon: IconBuildingWarehouse,
        perms: [Perm.INVENTORY_VIEW],
      },
      {
        label: 'Purchases',
        to: '/purchases',
        icon: IconTruckDelivery,
        perms: [Perm.INVENTORY_MANAGE],
      },
    ],
  },
  {
    label: 'Insight',
    items: [
      { label: 'Insights', to: '/insights', icon: IconChartDots3, perms: [Perm.REPORTS_ALL] },
      {
        label: 'Reports',
        to: '/reports',
        icon: IconChartBar,
        perms: [Perm.REPORTS_ALL, Perm.REPORTS_DAILY_SALES, Perm.REPORTS_OWN_PRODUCTION],
      },
      {
        label: 'Settings',
        to: '/settings',
        icon: IconSettings,
        perms: [
          Perm.SETTINGS_MANAGE,
          Perm.CATALOG_MANAGE,
          Perm.USERS_MANAGE,
          Perm.AUDIT_VIEW,
          Perm.SYSTEM_BACKUP,
        ],
      },
    ],
  },
];
