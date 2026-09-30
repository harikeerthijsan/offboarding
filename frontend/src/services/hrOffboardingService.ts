import api from './api';
import type {
  HRDashboardData, HROffboardingRow, OffboardingSummary, PaginatedResponse,
} from '../types';

export interface OffboardingListFilters {
  search?: string;
  department?: number | string;
  manager?: number | string;
  status?: string;
  final_review_status?: string;
  settlement_status?: string;
  exit_interview_status?: string;
  stage?: string;
  resignation_date_from?: string;
  resignation_date_to?: string;
  page?: number;
  page_size?: number;
}

export const hrOffboardingService = {
  dashboard: async (): Promise<HRDashboardData> => {
    const { data } = await api.get('/offboarding/dashboard/');
    return data;
  },
  list: async (filters?: OffboardingListFilters): Promise<PaginatedResponse<HROffboardingRow>> => {
    const { data } = await api.get('/offboarding/dashboard/list/', { params: filters || {} });
    return data;
  },
  summary: async (id: number): Promise<OffboardingSummary> => {
    const { data } = await api.get(`/offboarding/${id}/summary/`);
    return data;
  },
  startFinalReview: async (id: number, finalReviewDate: string, comments?: string): Promise<OffboardingSummary> => {
    const { data } = await api.post(`/offboarding/${id}/final-review/start/`, {
      final_review_date: finalReviewDate, comments: comments ?? '',
    });
    return data;
  },
  approveFinalReview: async (id: number, finalApprovalDate: string, comments?: string): Promise<OffboardingSummary> => {
    const { data } = await api.post(`/offboarding/${id}/final-review/approve/`, {
      final_approval_date: finalApprovalDate, comments: comments ?? '',
    });
    return data;
  },
  rejectFinalReview: async (id: number, rejectionReason: string): Promise<OffboardingSummary> => {
    const { data } = await api.post(`/offboarding/${id}/final-review/reject/`, {
      rejection_reason: rejectionReason,
    });
    return data;
  },
};
