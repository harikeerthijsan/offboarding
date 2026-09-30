import type { DepartmentClearanceStatus, AssetClearanceStatus, AssetStatus } from '../types';

export const DEPT_STATUS_BADGE: Record<DepartmentClearanceStatus, string> = {
  PENDING: 'badge-clr-pending',
  IN_PROGRESS: 'badge-clr-in-progress',
  CLEARED: 'badge-cleared',
  REJECTED: 'badge-clr-rejected',
  NOT_APPLICABLE: 'badge-clr-na',
};

export const ASSET_CLR_STATUS_BADGE: Record<AssetClearanceStatus, string> = {
  RETURN_PENDING: 'badge-return-pending',
  RETURNED: 'badge-returned',
  CLEARED: 'badge-cleared',
  DAMAGED: 'badge-damaged',
  LOST: 'badge-lost',
  REJECTED: 'badge-clr-rejected',
};

export const ASSET_STATUS_BADGE: Record<AssetStatus, string> = {
  ASSIGNED: 'badge-assigned',
  RETURN_PENDING: 'badge-return-pending',
  RETURNED: 'badge-returned',
  LOST: 'badge-lost',
  DAMAGED: 'badge-damaged',
  CLEARED: 'badge-cleared',
};

export const ASSET_TYPES: { value: string; label: string }[] = [
  { value: 'LAPTOP', label: 'Laptop' },
  { value: 'DESKTOP', label: 'Desktop' },
  { value: 'MONITOR', label: 'Monitor' },
  { value: 'MOBILE', label: 'Mobile' },
  { value: 'TABLET', label: 'Tablet' },
  { value: 'KEYBOARD', label: 'Keyboard' },
  { value: 'MOUSE', label: 'Mouse' },
  { value: 'HEADSET', label: 'Headset' },
  { value: 'ID_CARD', label: 'ID Card' },
  { value: 'ACCESS_CARD', label: 'Access Card' },
  { value: 'SIM_CARD', label: 'SIM Card' },
  { value: 'OTHER', label: 'Other' },
];

export const ASSET_CONDITIONS: { value: string; label: string }[] = [
  { value: 'GOOD', label: 'Good' },
  { value: 'FAIR', label: 'Fair' },
  { value: 'DAMAGED', label: 'Damaged' },
  { value: 'NON_FUNCTIONAL', label: 'Non Functional' },
];

export const CLEARANCE_DEPARTMENTS: { value: string; label: string }[] = [
  { value: 'IT', label: 'IT' },
  { value: 'ADMIN', label: 'Admin' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'HR', label: 'HR' },
  { value: 'MANAGER', label: 'Manager' },
];
