import api from './api';
import type { NoticePeriod, ResignationRequest } from '../types';

export interface NoticePeriodPayload {
  notice_period_start_date?: string | null;
  notice_period_days?: number | null;
  expected_last_working_day?: string | null;
  actual_last_working_day?: string | null;
  /** Optional HR-entered early relieving date; null clears a recorded early release. */
  early_relief_date?: string | null;
  notice_comments?: string;
}

export const noticePeriodService = {
  get: async (resignationId: number): Promise<NoticePeriod> => {
    const { data } = await api.get(`/offboarding/${resignationId}/notice-period/`);
    return data;
  },

  create: async (resignationId: number, payload: NoticePeriodPayload): Promise<NoticePeriod> => {
    const { data } = await api.post(`/offboarding/${resignationId}/notice-period/`, payload);
    return data;
  },

  update: async (resignationId: number, payload: NoticePeriodPayload): Promise<NoticePeriod> => {
    const { data } = await api.patch(`/offboarding/${resignationId}/notice-period/`, payload);
    return data;
  },

  requestEarlyRelease: async (resignationId: number, reason: string): Promise<NoticePeriod> => {
    const { data } = await api.post(`/offboarding/${resignationId}/early-release/`, {
      action: 'request',
      reason,
    });
    return data;
  },

  reviewEarlyRelease: async (
    resignationId: number,
    action: 'approve' | 'reject',
    earlyReleaseDate?: string | null,
    notes?: string,
  ): Promise<NoticePeriod> => {
    const { data } = await api.post(`/offboarding/${resignationId}/early-release/`, {
      action,
      early_release_date: earlyReleaseDate ?? null,
      notes: notes ?? '',
    });
    return data;
  },

  recordExtension: async (
    resignationId: number,
    noticeExtensionDate: string,
    extensionReason: string,
  ): Promise<NoticePeriod> => {
    const { data } = await api.post(`/offboarding/${resignationId}/notice-extension/`, {
      notice_extension_date: noticeExtensionDate,
      extension_reason: extensionReason,
    });
    return data;
  },

  complete: async (
    resignationId: number,
    actualLastWorkingDay: string,
  ): Promise<ResignationRequest> => {
    const { data } = await api.post(`/offboarding/${resignationId}/notice-period/complete/`, {
      actual_last_working_day: actualLastWorkingDay,
    });
    return data;
  },
};
