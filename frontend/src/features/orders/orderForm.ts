/** Order form values and conversion to/from the API. */
import dayjs from 'dayjs';

import type { OrderDetail, OrderItemWrite, OrderWrite } from '@/api/types';
import { toNumber } from '@/lib/format';

export interface AddOnValue {
  addon: string;
  quantity: number | string;
}

export interface ItemValue {
  key: string;
  id: number | null;
  media_type: string | null;
  /** Priced per piece: size optional, no minimum. Copied from the media when chosen. */
  per_piece: boolean;
  /** Empty = rate card (or the rate the order was quoted at). */
  rate: number | string;
  description: string;
  width: number | string;
  height: number | string;
  unit: 'ft' | 'in' | 'cm';
  quantity: number | string;
  finishing: string;
  design_file_ref: string;
  addons: AddOnValue[];
}

export interface OrderFormValues {
  deadline: string | null;
  is_urgent: boolean;
  notes: string;
  discount_type: 'none' | 'percent' | 'amount';
  discount_value: number | string;
  items: ItemValue[];
}

let counter = 0;
export const newKey = () => `item-${Date.now()}-${counter++}`;

export function emptyItem(
  unit: ItemValue['unit'] = 'ft',
  mediaType: string | null = null,
): ItemValue {
  return {
    key: newKey(),
    id: null,
    media_type: mediaType,
    per_piece: false,
    rate: '',
    description: '',
    width: '',
    height: '',
    unit,
    quantity: 1,
    finishing: '',
    design_file_ref: '',
    addons: [],
  };
}

export function defaultDeadline(): string {
  // Tomorrow at 5 PM: the usual promise at the counter.
  return dayjs().add(1, 'day').hour(17).minute(0).second(0).format('YYYY-MM-DD HH:mm:ss');
}

export function initialValues(order?: OrderDetail): OrderFormValues {
  if (!order) {
    return {
      deadline: defaultDeadline(),
      is_urgent: false,
      notes: '',
      discount_type: 'none',
      discount_value: 0,
      items: [emptyItem()],
    };
  }
  return {
    deadline: order.deadline ? dayjs(order.deadline).format('YYYY-MM-DD HH:mm:ss') : null,
    is_urgent: order.is_urgent,
    notes: order.notes ?? '',
    discount_type: (order.discount_type ?? 'none') as OrderFormValues['discount_type'],
    discount_value: toNumber(order.discount_value),
    items: order.items.map((item) => ({
      key: newKey(),
      id: item.id,
      media_type: String(item.media_type),
      per_piece: item.pricing_unit === 'piece',
      rate: toNumber(item.rate),
      description: item.description ?? '',
      width: item.has_size ? toNumber(item.width) : '',
      height: item.has_size ? toNumber(item.height) : '',
      unit: item.unit as ItemValue['unit'],
      quantity: item.quantity,
      finishing: item.finishing ?? '',
      design_file_ref: item.design_file_ref ?? '',
      addons: item.addons.map((a) => ({ addon: String(a.addon), quantity: toNumber(a.quantity) })),
    })),
  };
}

export function isItemComplete(item: ItemValue): boolean {
  const sized = toNumber(item.width) > 0 && toNumber(item.height) > 0;
  const noSize = toNumber(item.width) === 0 && toNumber(item.height) === 0;
  return !!item.media_type && (sized || (item.per_piece && noSize)) && toNumber(item.quantity) >= 1;
}

export function itemPayload(item: ItemValue): OrderItemWrite {
  return {
    id: item.id,
    media_type: Number(item.media_type),
    description: item.description.trim(),
    width: String(toNumber(item.width)),
    height: String(toNumber(item.height)),
    unit: item.unit,
    quantity: Math.max(1, Math.round(toNumber(item.quantity))),
    rate: item.rate === '' ? null : String(toNumber(item.rate)),
    finishing: item.finishing.trim(),
    design_file_ref: item.design_file_ref.trim(),
    addons: item.addons.map((a) => ({
      addon: Number(a.addon),
      quantity: String(toNumber(a.quantity)),
    })),
  };
}

export function pricingPayload(values: OrderFormValues) {
  return {
    discount_type: values.discount_type,
    discount_value: String(toNumber(values.discount_value)),
    items: values.items.filter(isItemComplete).map(itemPayload),
  };
}

export function orderPayload(
  values: OrderFormValues,
  customerId: number,
  confirm: boolean,
): OrderWrite {
  return {
    customer: customerId,
    deadline: values.deadline ? dayjs(values.deadline).toISOString() : null,
    is_urgent: values.is_urgent,
    notes: values.notes.trim(),
    discount_type: values.discount_type,
    discount_value: String(toNumber(values.discount_value)),
    items: values.items.map(itemPayload),
    confirm,
  };
}
