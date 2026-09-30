import api from './api';
import type {
  KTListItem, KnowledgeTransfer, KTSummary, KTDocument, Project, KTPriority,
} from '../types';

export interface KTCreatePayload {
  title: string;
  description?: string;
  project?: number | null;
  responsibility?: string;
  receiver: number;
  priority: KTPriority;
  start_date?: string | null;
  target_completion_date?: string | null;
}

export interface KTFilters {
  status?: string;
  priority?: string;
  project?: number | string;
  receiver?: number | string;
  assigned_to?: number | string;
  search?: string;
  ordering?: string;
}

export const ktService = {
  // Projects
  listProjects: async (activeOnly = true): Promise<Project[]> => {
    const params = activeOnly ? { active: 'true' } : {};
    const { data } = await api.get('/projects/', { params });
    return data;
  },
  createProject: async (payload: Partial<Project>): Promise<Project> => {
    const { data } = await api.post('/projects/', payload);
    return data;
  },

  // KT per offboarding
  list: async (offboardingId: number, filters?: KTFilters): Promise<KTListItem[]> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/kt/`, { params: filters || {} });
    return data;
  },
  create: async (offboardingId: number, payload: KTCreatePayload): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/kt/`, payload);
    return data;
  },
  summary: async (offboardingId: number): Promise<KTSummary> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/kt/summary/`);
    return data;
  },
  markPhaseComplete: async (offboardingId: number): Promise<{ detail: string }> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/kt/complete/`);
    return data;
  },

  // Single KT
  get: async (ktId: number): Promise<KnowledgeTransfer> => {
    const { data } = await api.get(`/kt/${ktId}/`);
    return data;
  },
  update: async (ktId: number, payload: Partial<KTCreatePayload> & { completion_notes?: string }): Promise<KnowledgeTransfer> => {
    const { data } = await api.patch(`/kt/${ktId}/`, payload);
    return data;
  },
  start: async (ktId: number): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/kt/${ktId}/start/`);
    return data;
  },
  submit: async (ktId: number): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/kt/${ktId}/submit/`);
    return data;
  },
  receiverAction: async (ktId: number, action: 'accept' | 'request_changes', comments?: string): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/kt/${ktId}/receiver-action/`, { action, comments: comments ?? '' });
    return data;
  },
  managerAction: async (
    ktId: number,
    action: 'approve' | 'request_changes',
    opts: { completed_date?: string | null; comments?: string },
  ): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/kt/${ktId}/manager-action/`, {
      action,
      completed_date: opts.completed_date ?? null,
      comments: opts.comments ?? '',
    });
    return data;
  },
  reassign: async (ktId: number, receiver: number, comments?: string): Promise<KnowledgeTransfer> => {
    const { data } = await api.post(`/kt/${ktId}/reassign/`, { receiver, comments: comments ?? '' });
    return data;
  },

  // Mine
  mine: async (role?: 'assigned' | 'receiver', statusFilter?: string): Promise<KTListItem[]> => {
    const params: Record<string, string> = {};
    if (role) params.role = role;
    if (statusFilter) params.status = statusFilter;
    const { data } = await api.get('/kt/mine/', { params });
    return data;
  },

  // Documents
  listDocuments: async (ktId: number): Promise<KTDocument[]> => {
    const { data } = await api.get(`/kt/${ktId}/documents/`);
    return data;
  },
  addDocument: async (ktId: number, url: string, description?: string): Promise<KTDocument> => {
    const { data } = await api.post(`/kt/${ktId}/documents/`, { url, description: description ?? '' });
    return data;
  },
  deleteDocument: async (ktId: number, docId: number): Promise<void> => {
    await api.delete(`/kt/${ktId}/documents/${docId}/`);
  },
};
