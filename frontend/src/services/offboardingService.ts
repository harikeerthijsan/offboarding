import api from './api';
import type { ResignationListItem, ResignationRequest } from '../types';

export interface CreateResignationPayload {
  reason: string;
  notes?: string;
}

export const offboardingService = {
  listResignations: async (statusFilter?: string): Promise<ResignationListItem[]> => {
    const params = statusFilter ? { status: statusFilter } : {};
    const { data } = await api.get('/offboarding/', { params });
    return data;
  },

  getResignation: async (id: number): Promise<ResignationRequest> => {
    const { data } = await api.get(`/offboarding/${id}/`);
    return data;
  },

  createResignation: async (payload: CreateResignationPayload): Promise<ResignationRequest> => {
    const { data } = await api.post('/offboarding/', payload);
    return data;
  },

  submitResignation: async (id: number): Promise<ResignationRequest> => {
    const { data } = await api.post(`/offboarding/${id}/submit/`);
    return data;
  },

  managerAction: async (
    id: number,
    action: 'approve' | 'reject',
    notes?: string,
  ): Promise<ResignationRequest> => {
    const { data } = await api.post(`/offboarding/${id}/manager-action/`, {
      action,
      notes: notes ?? '',
    });
    return data;
  },

  hrAction: async (
    id: number,
    action: 'approve' | 'reject',
    notes?: string,
  ): Promise<ResignationRequest> => {
    const { data } = await api.post(`/offboarding/${id}/hr-action/`, {
      action,
      notes: notes ?? '',
    });
    return data;
  },

  cancelResignation: async (id: number, reason?: string): Promise<ResignationRequest> => {
    const { data } = await api.post(`/offboarding/${id}/cancel/`, { reason: reason ?? '' });
    return data;
  },
};
