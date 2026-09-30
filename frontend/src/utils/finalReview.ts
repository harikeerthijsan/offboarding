import type { FinalReviewStatus, SectionStatus } from '../types';

export const FINAL_REVIEW_BADGE: Record<FinalReviewStatus, string> = {
  NOT_READY: 'badge-fr-not-ready',
  READY_FOR_REVIEW: 'badge-fr-ready',
  UNDER_REVIEW: 'badge-fr-under-review',
  APPROVED: 'badge-fr-approved',
  REJECTED: 'badge-fr-rejected',
};

export const FINAL_REVIEW_LABEL: Record<FinalReviewStatus, string> = {
  NOT_READY: 'Not Ready',
  READY_FOR_REVIEW: 'Ready for Review',
  UNDER_REVIEW: 'Under Review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};

export const SECTION_ICON: Record<SectionStatus, string> = {
  COMPLETE: '✓',
  IN_PROGRESS: '●',
  REJECTED: '✕',
  PENDING: '○',
  NOT_APPLICABLE: '–',
};

export const SECTION_LABEL: Record<SectionStatus, string> = {
  COMPLETE: 'Complete',
  IN_PROGRESS: 'In Progress',
  REJECTED: 'Rejected',
  PENDING: 'Pending',
  NOT_APPLICABLE: 'N/A',
};

export function sectionDotClass(s: SectionStatus): string {
  return `sec-dot ${s.toLowerCase()}`;
}
