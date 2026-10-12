import api, { apiBaseUrl } from './api';
import type { Policy } from '../types';

export const policyService = {
  list: async (params?: { category?: string; search?: string }): Promise<Policy[]> => {
    const { data } = await api.get<Policy[]>('/policies/', { params: params || {} });
    return data;
  },

  upload: async (payload: {
    title: string; description?: string; category?: string; file: File;
  }): Promise<Policy> => {
    const form = new FormData();
    form.append('title', payload.title);
    form.append('description', payload.description ?? '');
    form.append('category', payload.category ?? 'OTHER');
    form.append('file', payload.file);
    const { data } = await api.post<Policy>('/policies/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  update: async (id: number, payload: Partial<Pick<Policy, 'title' | 'description' | 'category' | 'is_active'>>): Promise<Policy> => {
    const { data } = await api.patch<Policy>(`/policies/${id}/`, payload);
    return data;
  },

  remove: async (id: number): Promise<void> => {
    await api.delete(`/policies/${id}/`);
  },

  downloadUrl: (id: number): string => `${apiBaseUrl}/policies/${id}/download/`,
};
