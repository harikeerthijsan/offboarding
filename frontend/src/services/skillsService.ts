import api from './api';
import type {
  MySkillsResponse, SkillsPicker, SkillItem, SkillSubmission,
  CatalogueSkill, CycleRow, SkillsTeamRow,
} from '../types';

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
