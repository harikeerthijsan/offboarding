import api from './api';
import type {
  Asset, AssetClearance, DepartmentClearance, ChecklistItem,
  ClearanceSummary, ClearanceDepartment, AssetCondition,
} from '../types';

export interface AssetFilters {
  asset_type?: string;
  status?: string;
  condition?: string;
  assigned_to?: number | string;
  search?: string;
}

export interface ClearanceQueueRow {
  offboarding_id: number;
  department: string;
  department_display: string;
  status: string;
  status_display: string;
  employee_name: string;
  employee_id: string;
  employee_department: string;
  pending_assets: number;
}

export const clearanceService = {
  queue: async (): Promise<ClearanceQueueRow[]> => {
    const { data } = await api.get('/clearances/queue/');
    return data;
  },

  // Assets catalogue
  listAssets: async (filters?: AssetFilters): Promise<Asset[]> => {
    const { data } = await api.get('/assets/', { params: filters || {} });
    return data;
  },
  createAsset: async (payload: Partial<Asset>): Promise<Asset> => {
    const { data } = await api.post('/assets/', payload);
    return data;
  },
  updateAsset: async (id: number, payload: Partial<Asset>): Promise<Asset> => {
    const { data } = await api.patch(`/assets/${id}/`, payload);
    return data;
  },
  employeeAssets: async (employeeId: number): Promise<Asset[]> => {
    const { data } = await api.get(`/employees/${employeeId}/assets/`);
    return data;
  },

  // Asset clearance (per offboarding)
  listAssetClearances: async (offboardingId: number, filters?: AssetFilters): Promise<AssetClearance[]> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/assets/`, { params: filters || {} });
    return data;
  },
  addAssetClearance: async (offboardingId: number, assetId: number): Promise<AssetClearance> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/assets/`, { asset: assetId });
    return data;
  },
  recordReturn: async (
    acId: number, returnDate: string, condition: AssetCondition, remarks?: string,
  ): Promise<AssetClearance> => {
    const { data } = await api.patch(`/asset-clearance/${acId}/`, {
      action: 'record_return', return_date: returnDate, condition, remarks: remarks ?? '',
    });
    return data;
  },
  verifyAsset: async (
    acId: number, action: 'verify' | 'reject' | 'mark_damaged' | 'mark_lost', comments?: string,
  ): Promise<AssetClearance> => {
    const { data } = await api.patch(`/asset-clearance/${acId}/`, { action, comments: comments ?? '' });
    return data;
  },

  // Department clearance
  listClearances: async (offboardingId: number): Promise<DepartmentClearance[]> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/clearances/`);
    return data;
  },
  createClearance: async (offboardingId: number, department: ClearanceDepartment, assignedTo?: number): Promise<DepartmentClearance> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/clearances/`, {
      department, assigned_to: assignedTo ?? null,
    });
    return data;
  },
  clearanceAction: async (
    clearanceId: number,
    action: 'clear' | 'reject' | 'in_progress' | 'not_applicable' | 'reopen',
    opts: { clearance_date?: string | null; comments?: string },
  ): Promise<DepartmentClearance> => {
    const { data } = await api.patch(`/clearances/${clearanceId}/`, {
      action, clearance_date: opts.clearance_date ?? null, comments: opts.comments ?? '',
    });
    return data;
  },

  // Checklist
  listChecklist: async (clearanceId: number): Promise<ChecklistItem[]> => {
    const { data } = await api.get(`/clearances/${clearanceId}/checklist/`);
    return data;
  },
  addChecklistItem: async (clearanceId: number, title: string, description?: string): Promise<ChecklistItem> => {
    const { data } = await api.post(`/clearances/${clearanceId}/checklist/`, { title, description: description ?? '' });
    return data;
  },
  checklistAction: async (
    itemId: number,
    action: 'complete' | 'not_applicable' | 'reset' | 'reject',
    comments?: string,
  ): Promise<ChecklistItem> => {
    const { data } = await api.patch(`/checklist/${itemId}/`, { action, comments: comments ?? '' });
    return data;
  },

  // Summary & completion
  summary: async (offboardingId: number): Promise<ClearanceSummary> => {
    const { data } = await api.get(`/offboarding/${offboardingId}/clearance/summary/`);
    return data;
  },
  markComplete: async (offboardingId: number): Promise<{ detail: string }> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/clearance/complete/`);
    return data;
  },

  // Employee asset-return declaration
  submitAssetDeclaration: async (
    offboardingId: number,
    notes?: string,
    items?: { item: string; status: string }[],
  ): Promise<{ detail: string; asset_declaration_at: string; asset_declaration_notes: string }> => {
    const { data } = await api.post(`/offboarding/${offboardingId}/asset-declaration/`, {
      notes: notes ?? '', items: items ?? [],
    });
    return data;
  },
};
