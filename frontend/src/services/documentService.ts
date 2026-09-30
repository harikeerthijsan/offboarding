import api, { apiBaseUrl } from './api';
import type { OffboardingDocument, CompanyProfile, DocumentType } from '../types';

export type DocumentAction =
  | 'submit_review' | 'approve' | 'reject' | 'release' | 'revoke' | 'regenerate';

export const documentService = {
  list: async (offboardingId: number): Promise<OffboardingDocument[]> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/documents/`);
    return data;
  },
  generate: async (
    offboardingId: number, documentType: DocumentType,
    documentDate?: string | null, title?: string,
  ): Promise<OffboardingDocument> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/documents/`, {
      document_type: documentType,
      document_date: documentDate || null,
      document_title: title ?? '',
    });
    return data;
  },
  get: async (id: number): Promise<OffboardingDocument> => {
    const { data } = await api.get(`/documents/${id}/`);
    return data;
  },
  action: async (
    id: number, action: DocumentAction,
    opts: { reason?: string; document_date?: string | null } = {},
  ): Promise<OffboardingDocument> => {
    const { data } = await api.post(`/documents/${id}/action/`, {
      action, reason: opts.reason ?? '', document_date: opts.document_date ?? null,
    });
    return data;
  },
  downloadUrl: (id: number): string => `${apiBaseUrl}/documents/${id}/download/`,

  getCompanyProfile: async (): Promise<CompanyProfile> => {
    const { data } = await api.get('/company-profile/');
    return data;
  },
  updateCompanyProfile: async (payload: Partial<CompanyProfile>): Promise<CompanyProfile> => {
    const { data } = await api.put('/company-profile/', payload);
    return data;
  },
};
