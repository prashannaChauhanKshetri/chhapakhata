/** Friendly names for the generated API types. */
import type { components } from './schema';

type S = components['schemas'];

export type Me = S['Me'];
export type User = S['User'];
export type UserRef = S['UserRef'];
export type ShopSettings = S['ShopSettings'];
export type ActivityLog = S['ActivityLog'];
export type DateConversion = S['DateConversion'];

export type Customer = S['Customer'];
export type CustomerRef = S['CustomerRef'];
export type Statement = S['Statement'];
export type StatementEntry = S['StatementEntry'];

export type MediaType = S['MediaType'];
export type AddOn = S['AddOn'];
export type RateHistory = S['RateHistory'];

export type OrderList = S['OrderList'];
export type OrderDetail = S['OrderDetail'];
export type OrderItem = S['OrderItem'];
export type OrderWrite = S['OrderWriteRequest'];
export type OrderItemWrite = S['OrderItemWriteRequest'];
export type PricePreview = S['PricePreview'];
export type ItemResult = S['ItemResult'];

export type Job = S['Job'];
export type JobDetail = S['JobDetail'];
export type Board = S['Board'];
export type BoardColumn = S['BoardColumn'];
export type MaterialOptions = S['MaterialOptions'];
export type MoveResult = S['MoveResult'];

export type InvoiceList = S['InvoiceList'];
export type InvoiceDetail = S['InvoiceDetail'];
export type Payment = S['Payment'];
export type PaymentCreate = S['PaymentCreateRequest'];

export type StockItem = S['StockItem'];
export type Roll = S['Roll'];
export type Supplier = S['Supplier'];
export type Purchase = S['Purchase'];
export type StockMovement = S['StockMovement'];

export type BackupRun = S['BackupRun'];

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Report payload (generic, rendered by the reports page). */
export type ReportColumnKind = 'text' | 'money' | 'number' | 'sqft' | 'date' | 'percent';
export interface ReportColumn {
  key: string;
  label: string;
  kind: ReportColumnKind;
}
export interface ReportTable {
  title: string;
  columns: ReportColumn[];
  rows: Record<string, string | number | null>[];
  totals: Record<string, string | number | null> | null;
  empty_message: string;
}
export interface Report {
  slug: string;
  title: string;
  period: string;
  params: Record<string, string>;
  summary: { label: string; value: string | number; kind: ReportColumnKind }[];
  tables: ReportTable[];
}
export interface ReportInfo {
  slug: string;
  title: string;
  date_range: boolean;
}

/** Dashboard payload; sections appear only when the user may see them. */
export interface Dashboard {
  date: string;
  date_bs: string;
  today?: {
    sales: string;
    invoices: number;
    collections: string;
    payments: number;
    orders: number;
    quotations: number;
  };
  ready_orders?: { id: number; order_no: string; customer: string; phone: string; total: string }[];
  dues?: { total: string; customers: number; over_90_days: string };
  sales_trend?: { date: string; date_bs: string; total: number }[];
  backup?: {
    last_run_at: string | null;
    last_run_status: string | null;
    last_success_at: string | null;
    offsite_status: string | null;
    is_stale: boolean;
  };
  jobs?: {
    open: number;
    overdue: number;
    due_today: number;
    by_stage: { stage: number; label: string; count: number }[];
  };
  overdue_jobs?: {
    id: number;
    job_no: string;
    customer: string;
    media: string;
    stage_label: string;
    deadline: string | null;
  }[];
  low_stock?: {
    id: number;
    name: string;
    on_hand: string;
    low_stock_level: string;
    unit: string;
  }[];
  recent_payments?: {
    id: number;
    receipt_no: string;
    customer: string;
    amount: string;
    mode: string;
    payment_date: string;
  }[];
  my_production?: { jobs: number; sqft: string; period_start: string };
}
