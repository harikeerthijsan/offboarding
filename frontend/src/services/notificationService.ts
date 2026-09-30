import api from './api';
import type { NotificationItem, PaginatedResponse } from '../types';

function unwrap<T>(data: PaginatedResponse<T> | T[]): T[] {
  if (Array.isArray(data)) return data;
  return data.results;
}

export const notificationService = {
  list: async (unreadOnly = false): Promise<NotificationItem[]> => {
    const { data } = await api.get('/notifications/', {
      params: unreadOnly ? { unread: 'true' } : {},
    });
    return unwrap<NotificationItem>(data);
  },

  unreadCount: async (): Promise<number> => {
    const { data } = await api.get('/notifications/unread-count/');
    return data.unread_count;
  },

  markRead: async (id: number): Promise<void> => {
    await api.post(`/notifications/${id}/read/`);
  },

  markAllRead: async (): Promise<void> => {
    await api.post('/notifications/read-all/');
  },
};
