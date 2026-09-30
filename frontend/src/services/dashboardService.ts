import api from './api';

export interface StatMetric { value: number; trend: number; }

export interface DashboardOverview {
  stats: {
    total_employees: StatMetric;
    active: StatMetric;
    offboarding: StatMetric;
    exited: StatMetric;
    departments: StatMetric;
  };
  pipeline: {
    resignation: number; notice: number; kt: number; clearance: number;
    settlement: number; exit_interview: number; final_review: number; completed: number;
  };
  status: {
    total: number;
    completed: number; completed_pct: number;
    in_progress: number; in_progress_pct: number;
    pending: number; pending_pct: number;
    rejected: number; rejected_pct: number;
  };
  departments: { name: string; count: number }[];
  recent_activity: { action: string; label: string; target: string; when: string; category: string }[];
  recent_exits: { name: string; employee_id: string; department: string; date: string }[];
  upcoming_tasks: { title: string; subtitle: string; due: string | null; priority: string }[];
  trends: { labels: string[]; new: number[]; completed: number[]; pending: number[] };
}

export const dashboardService = {
  overview: async (): Promise<DashboardOverview> => {
    const { data } = await api.get('/offboarding/dashboard/overview/');
    return data;
  },
};
