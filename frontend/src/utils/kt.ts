import type { KTStatus, KTPriority } from '../types';

export const KT_STATUS_BADGE: Record<KTStatus, string> = {
  PENDING: 'badge-pending',
  IN_PROGRESS: 'badge-in-progress',
  SUBMITTED: 'badge-submitted',
  RECEIVER_REVIEW: 'badge-receiver-review',
  MANAGER_REVIEW: 'badge-manager-review',
  COMPLETED: 'badge-completed',
  REJECTED: 'badge-rejected',
};

export const KT_PRIORITY_BADGE: Record<KTPriority, string> = {
  LOW: 'badge-prio-low',
  MEDIUM: 'badge-prio-medium',
  HIGH: 'badge-prio-high',
  CRITICAL: 'badge-prio-critical',
};

export function formatDate(d: string | null | undefined): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch { return d; }
}

export function formatDateTime(d: string | null | undefined): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return d; }
}

export function ktErrorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: Record<string, unknown>; status?: number } };
  const data = e?.response?.data;
  if (data) {
    if (typeof data.detail === 'string') return data.detail;
    const firstKey = Object.keys(data)[0];
    if (firstKey) {
      const val = data[firstKey];
      if (Array.isArray(val)) return `${firstKey}: ${val[0]}`;
      if (typeof val === 'string') return `${firstKey}: ${val}`;
    }
  }
  return fallback;
}
