/** Mirrors backend/apps/core/permissions.py `Perm`. The server enforces every rule;
 * the UI only hides what a user cannot use. */
export const Perm = {
  CATALOG_VIEW: 'catalog.view',
  CATALOG_MANAGE: 'catalog.manage',
  CUSTOMERS_VIEW: 'customers.view',
  CUSTOMERS_MANAGE: 'customers.manage',
  ORDERS_VIEW: 'orders.view',
  ORDERS_MANAGE: 'orders.manage',
  DOCUMENTS_ISSUE: 'documents.issue',
  INVOICES_VIEW: 'invoices.view',
  INVOICES_CANCEL: 'invoices.cancel',
  PAYMENTS_VIEW: 'payments.view',
  PAYMENTS_RECEIVE: 'payments.receive',
  PAYMENTS_VOID: 'payments.void',
  LEDGER_VIEW: 'ledger.view',
  LEDGER_MANAGE: 'ledger.manage',
  PRODUCTION_VIEW: 'production.view',
  PRODUCTION_MOVE: 'production.move',
  INVENTORY_VIEW: 'inventory.view',
  INVENTORY_RECORD_USAGE: 'inventory.record_usage',
  INVENTORY_MANAGE: 'inventory.manage',
  REPORTS_ALL: 'reports.all',
  REPORTS_DAILY_SALES: 'reports.daily_sales',
  REPORTS_OWN_PRODUCTION: 'reports.own_production',
  DASHBOARD_SALES: 'dashboard.sales',
  USERS_MANAGE: 'users.manage',
  SETTINGS_MANAGE: 'settings.manage',
  AUDIT_VIEW: 'audit.view',
  SYSTEM_BACKUP: 'system.backup',
} as const;

export type PermName = (typeof Perm)[keyof typeof Perm];

export const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner (Admin)',
  front_desk: 'Front desk / Sales',
  operator: 'Production operator',
};
