import { describe, expect, it } from 'vitest';

import {
  emptyItem,
  isItemComplete,
  itemPayload,
  orderPayload,
  pricingPayload,
  type OrderFormValues,
} from './orderForm';

const values = (): OrderFormValues => ({
  deadline: '2026-10-16 17:00:00',
  is_urgent: true,
  notes: '  Call before delivery  ',
  discount_type: 'percent',
  discount_value: 5,
  items: [
    {
      ...emptyItem(),
      media_type: '1',
      width: 10,
      height: 4,
      quantity: 2,
      addons: [{ addon: '3', quantity: 8 }],
    },
    { ...emptyItem(), media_type: null, width: 3, height: 2 },
  ],
});

describe('order form payloads', () => {
  it('only prices complete rows', () => {
    const v = values();
    expect(isItemComplete(v.items[0])).toBe(true);
    expect(isItemComplete(v.items[1])).toBe(false);
    const pricing = pricingPayload(v);
    expect(pricing.items).toHaveLength(1);
    expect(pricing.discount_value).toBe('5');
  });

  it('sends decimals as strings and trims text', () => {
    const item = itemPayload(values().items[0]);
    expect(item).toMatchObject({
      media_type: 1,
      width: '10',
      height: '4',
      quantity: 2,
      unit: 'ft',
    });
    expect(item.addons).toEqual([{ addon: 3, quantity: '8' }]);
    const order = orderPayload(values(), 42, true);
    expect(order.customer).toBe(42);
    expect(order.confirm).toBe(true);
    expect(order.notes).toBe('Call before delivery');
    expect(order.deadline).toMatch(/^2026-10-16T/);
  });

  it('never sends a quantity below 1', () => {
    expect(
      itemPayload({ ...emptyItem(), media_type: '1', width: 1, height: 1, quantity: 0 }).quantity,
    ).toBe(1);
  });
});

describe('per-piece items and rates', () => {
  it('lets per-piece items skip the size', () => {
    const photo = { ...emptyItem(), media_type: '7', per_piece: true, quantity: 4 };
    expect(isItemComplete(photo)).toBe(true);
    expect(isItemComplete({ ...photo, per_piece: false })).toBe(false);
    // Half a size is still a mistake.
    expect(isItemComplete({ ...photo, width: 2 })).toBe(false);
    expect(itemPayload(photo)).toMatchObject({ width: '0', height: '0', rate: null });
  });

  it('sends a chosen rate, or null for the rate card', () => {
    const item = { ...emptyItem(), media_type: '1', width: 3, height: 2 };
    expect(itemPayload(item).rate).toBeNull();
    expect(itemPayload({ ...item, rate: 30 }).rate).toBe('30');
  });
});
