import type { CycleState } from '../types';

export const SKILL_CATEGORIES = ['Technical', 'Domain', 'Tools', 'Soft skills', 'Certification', 'Other'];
export const PROFICIENCY = ['Beginner', 'Intermediate', 'Advanced', 'Expert'];
export const SKILL_STATUSES: { value: string; label: string }[] = [
  { value: 'current', label: 'Current' },
  { value: 'learned', label: 'Newly learned' },
  { value: 'in_progress', label: 'In progress' },
];

// Same wording as the source app's StatusTag so screens read consistently.
export const STATE_LABEL: Record<string, string> = {
  approved: 'Recorded',
  submitted: 'Submitted',
  rejected: 'Needs update',
  draft: 'Draft',
  open: 'Due',
  overdue: 'Overdue',
  missed: 'Not submitted',
  upcoming: 'Upcoming',
  no_cycle: 'No cycle',
};

export function stateBadgeClass(state: CycleState | string): string {
  switch (state) {
    case 'approved':
    case 'submitted': return 'badge-active';
    case 'draft': return 'badge-secondary';
    case 'open': return 'badge-it';
    case 'overdue':
    case 'rejected': return 'badge-offboarding';
    case 'missed': return 'badge-exited';
    case 'upcoming': return 'badge-employee';
    default: return 'badge-secondary';
  }
}

export function stateLabel(state: CycleState | string): string {
  return STATE_LABEL[state] || state;
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return d; }
}
