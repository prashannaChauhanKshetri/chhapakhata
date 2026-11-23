import { useQuery } from '@tanstack/react-query';

import { apiGet } from '@/api/http';
import type { AddOn, MediaType, ShopSettings } from '@/api/types';

export function useMediaTypes() {
  return useQuery({
    queryKey: ['catalog', 'media-types'],
    queryFn: () => apiGet<MediaType[]>('/api/v1/media-types/'),
    staleTime: 60_000,
    // A media typed on an order is added to the list when saved; a copy kept for
    // offline use (e.g. after reopening the app) must not hide it from the next order.
    refetchOnMount: 'always',
  });
}

export function useAddOns() {
  return useQuery({
    queryKey: ['catalog', 'addons'],
    queryFn: () => apiGet<AddOn[]>('/api/v1/addons/'),
    staleTime: 60_000,
  });
}

export function useShopSettings() {
  return useQuery({
    queryKey: ['settings', 'shop'],
    queryFn: () => apiGet<ShopSettings>('/api/v1/settings/shop/'),
    staleTime: 5 * 60_000,
  });
}
