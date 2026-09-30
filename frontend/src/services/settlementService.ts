import api from './api';
import type {
  FinalSettlement, FinalSettlementEmployeeView, ExitInterview, ExitInterviewAnalytics,
} from '../types';

export interface SettlementMoneyPayload {
  pending_salary?: string | number;
  leave_encashment?: string | number;
  bonus?: string | number;
  incentives?: string | number;
  other_additions?: string | number;
  notice_recovery?: string | number;
  loan_deduction?: string | number;
  advance_deduction?: string | number;
  other_deductions?: string | number;
  comments?: string;
  reason?: string;
}

export interface ExitInterviewAnswersPayload {
  interview_date?: string | null;
  primary_reason?: string;
  secondary_reason?: string;
  overall_experience?: number;
  manager_feedback?: number;
  work_environment_feedback?: number;
  role_feedback?: number;
  growth_feedback?: number;
  compensation_feedback?: number;
  what_went_well?: string;
  what_could_improve?: string;
  suggestions?: string;
  additional_comments?: string;
  would_recommend?: boolean | null;
  would_rejoin?: boolean | null;
}

export const settlementService = {
  // Settlement
  get: async (oid: number): Promise<FinalSettlement | FinalSettlementEmployeeView> => {
    const { data } = await api.get(`/offboarding/${oid}/settlement/`);
    return data;
  },
  create: async (oid: number, payload: SettlementMoneyPayload): Promise<FinalSettlement> => {
    const { data } = await api.post(`/offboarding/${oid}/settlement/`, payload);
    return data;
  },
  update: async (oid: number, payload: SettlementMoneyPayload): Promise<FinalSettlement> => {
    const { data } = await api.patch(`/offboarding/${oid}/settlement/`, payload);
    return data;
  },
  submit: async (oid: number): Promise<FinalSettlement> => {
    const { data } = await api.post(`/offboarding/${oid}/settlement/submit/`);
    return data;
  },
  approve: async (oid: number, settlementDate: string, comments?: string): Promise<FinalSettlement> => {
    const { data } = await api.post(`/offboarding/${oid}/settlement/approve/`, {
      settlement_date: settlementDate, comments: comments ?? '',
    });
    return data;
  },
  reject: async (oid: number, comments: string): Promise<FinalSettlement> => {
    const { data } = await api.post(`/offboarding/${oid}/settlement/reject/`, { comments });
    return data;
  },

  // Exit interview
  getInterview: async (oid: number): Promise<ExitInterview> => {
    const { data } = await api.get(`/offboarding/${oid}/exit-interview/`);
    return data;
  },
  startInterview: async (oid: number): Promise<ExitInterview> => {
    const { data } = await api.post(`/offboarding/${oid}/exit-interview/`);
    return data;
  },
  saveInterview: async (oid: number, payload: ExitInterviewAnswersPayload): Promise<ExitInterview> => {
    const { data } = await api.patch(`/offboarding/${oid}/exit-interview/`, payload);
    return data;
  },
  submitInterview: async (oid: number): Promise<ExitInterview> => {
    const { data } = await api.post(`/offboarding/${oid}/exit-interview/submit/`);
    return data;
  },
  reviewInterview: async (oid: number, hrReviewNotes: string): Promise<ExitInterview> => {
    const { data } = await api.post(`/offboarding/${oid}/exit-interview/review/`, {
      hr_review_notes: hrReviewNotes,
    });
    return data;
  },
  reopenInterview: async (oid: number): Promise<ExitInterview> => {
    const { data } = await api.post(`/offboarding/${oid}/exit-interview/review/`, { action: 'reopen' });
    return data;
  },
  analytics: async (): Promise<ExitInterviewAnalytics> => {
    const { data } = await api.get('/exit-interviews/analytics/');
    return data;
  },
};
