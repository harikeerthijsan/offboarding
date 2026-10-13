import api, { apiBaseUrl } from './api';
import type {
  MySkillsResponse, SkillsPicker, SkillItem, SkillSubmission,
  CatalogueSkill, CycleRow, SkillsTeamRow,
} from '../types';

export interface CyclePayload {
  cycle_id: string;
  period_start: string;
  period_end: string;
  employee_due: string;
  manager_due: string;
  closure_target: string;
  notes?: string;
}

export const skillsService = {
  me: async (): Promise<MySkillsResponse> => {
    const { data } = await api.get<MySkillsResponse>('/skills/me/');
    return data;
  },

  picker: async (): Promise<SkillsPicker> => {
    const { data } = await api.get<SkillsPicker>('/skills/picker/');
    return data;
  },

  saveSubmission: async (
    skills: SkillItem[], submit: boolean, employeeNote = '',
  ): Promise<{ submission: SkillSubmission }> => {
    const { data } = await api.post('/skills/submissions/', {
      skills, submit, employee_note: employeeNote,
    });
    return data;
  },

  cycles: async (): Promise<{ cycles: CycleRow[] }> => {
    const { data } = await api.get('/skills/cycles/');
    return data;
  },
  createCycle: async (payload: CyclePayload): Promise<CycleRow> => {
    const { data } = await api.post('/skills/cycles/', payload);
    return data;
  },
  updateCycle: async (id: number, payload: Partial<CyclePayload>): Promise<CycleRow> => {
    const { data } = await api.patch(`/skills/cycles/${id}/`, payload);
    return data;
  },
  deleteCycle: async (id: number): Promise<void> => {
    await api.delete(`/skills/cycles/${id}/`);
  },

  // Excel export (staff). Returns the URL; caller fetches with the auth header.
  exportUrl: (params?: { status?: string; cycle?: string }): string => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.cycle) q.set('cycle', params.cycle);
    const qs = q.toString();
    return `${apiBaseUrl}/skills/export/${qs ? `?${qs}` : ''}`;
  },

  // Catalogue (staff)
  catalogue: async (): Promise<{ skills: CatalogueSkill[] }> => {
    const { data } = await api.get('/skills/catalogue/');
    return data;
  },
  addCatalogue: async (payload: { name: string; tools?: string; customers?: string }): Promise<{ skill: CatalogueSkill }> => {
    const { data } = await api.post('/skills/catalogue/', payload);
    return data;
  },
  updateCatalogue: async (id: number, payload: Partial<{ name: string; tools: string; customers: string; active: boolean }>): Promise<{ skill: CatalogueSkill }> => {
    const { data } = await api.patch(`/skills/catalogue/${id}/`, payload);
    return data;
  },
  deleteCatalogue: async (id: number): Promise<void> => {
    await api.delete(`/skills/catalogue/${id}/`);
  },

  // Team (staff)
  team: async (): Promise<{ team: SkillsTeamRow[] }> => {
    const { data } = await api.get('/skills/team/');
    return data;
  },
};
