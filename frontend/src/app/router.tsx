import { lazy, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router';

import { RequirePerm } from '@/auth/RequirePerm';
import { Perm, type PermName } from '@/lib/permissions';

import { AppLayout } from './layout/AppLayout';
import { RouteError } from './RouteError';

const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'));
const OrdersPage = lazy(() => import('@/features/orders/OrdersPage'));
const OrderFormPage = lazy(() => import('@/features/orders/OrderFormPage'));
const OrderDetailPage = lazy(() => import('@/features/orders/OrderDetailPage'));
const BoardPage = lazy(() => import('@/features/production/BoardPage'));
const CustomersPage = lazy(() => import('@/features/customers/CustomersPage'));
const CustomerDetailPage = lazy(() => import('@/features/customers/CustomerDetailPage'));
const InvoicesPage = lazy(() => import('@/features/billing/InvoicesPage'));
const InvoiceDetailPage = lazy(() => import('@/features/billing/InvoiceDetailPage'));
const PaymentsPage = lazy(() => import('@/features/billing/PaymentsPage'));
const LedgerPage = lazy(() => import('@/features/billing/LedgerPage'));
const InventoryPage = lazy(() => import('@/features/inventory/InventoryPage'));
const StockItemPage = lazy(() => import('@/features/inventory/StockItemPage'));
const PurchasesPage = lazy(() => import('@/features/inventory/PurchasesPage'));
const PurchaseFormPage = lazy(() => import('@/features/inventory/PurchaseFormPage'));
const InsightsPage = lazy(() => import('@/features/insights/InsightsPage'));
const ReportsPage = lazy(() => import('@/features/reports/ReportsPage'));
const ReportPage = lazy(() => import('@/features/reports/ReportPage'));
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'));
const NotFoundPage = lazy(() => import('@/features/errors/NotFoundPage'));

const guard = (perm: PermName | PermName[], element: ReactNode) => (
  <RequirePerm perm={perm}>{element}</RequirePerm>
);

const REPORT_PERMS = [Perm.REPORTS_ALL, Perm.REPORTS_DAILY_SALES, Perm.REPORTS_OWN_PRODUCTION];
const SETTINGS_PERMS = [
  Perm.SETTINGS_MANAGE,
  Perm.CATALOG_MANAGE,
  Perm.USERS_MANAGE,
  Perm.AUDIT_VIEW,
  Perm.SYSTEM_BACKUP,
];

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'orders', element: guard(Perm.ORDERS_VIEW, <OrdersPage />) },
      { path: 'orders/new', element: guard(Perm.ORDERS_MANAGE, <OrderFormPage />) },
      { path: 'orders/:id', element: guard(Perm.ORDERS_VIEW, <OrderDetailPage />) },
      { path: 'orders/:id/edit', element: guard(Perm.ORDERS_MANAGE, <OrderFormPage />) },
      { path: 'production', element: guard(Perm.PRODUCTION_VIEW, <BoardPage />) },
      { path: 'customers', element: guard(Perm.CUSTOMERS_VIEW, <CustomersPage />) },
      { path: 'customers/:id', element: guard(Perm.CUSTOMERS_VIEW, <CustomerDetailPage />) },
      { path: 'invoices', element: guard(Perm.INVOICES_VIEW, <InvoicesPage />) },
      { path: 'invoices/:id', element: guard(Perm.INVOICES_VIEW, <InvoiceDetailPage />) },
      { path: 'payments', element: guard(Perm.PAYMENTS_VIEW, <PaymentsPage />) },
      { path: 'ledger', element: <Navigate to="/ledger/balances" replace /> },
      { path: 'ledger/:tab', element: guard(Perm.LEDGER_VIEW, <LedgerPage />) },
      { path: 'inventory', element: guard(Perm.INVENTORY_VIEW, <InventoryPage />) },
      { path: 'inventory/:id', element: guard(Perm.INVENTORY_VIEW, <StockItemPage />) },
      { path: 'purchases', element: guard(Perm.INVENTORY_MANAGE, <PurchasesPage />) },
      { path: 'purchases/new', element: guard(Perm.INVENTORY_MANAGE, <PurchaseFormPage />) },
      { path: 'insights', element: guard(Perm.REPORTS_ALL, <InsightsPage />) },
      { path: 'reports', element: guard(REPORT_PERMS, <ReportsPage />) },
      { path: 'reports/:slug', element: guard(REPORT_PERMS, <ReportPage />) },
      { path: 'settings', element: <Navigate to="/settings/shop" replace /> },
      { path: 'settings/:tab', element: guard(SETTINGS_PERMS, <SettingsPage />) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
