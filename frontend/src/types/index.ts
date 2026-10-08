export type UserRole = 'EMPLOYEE' | 'MANAGER' | 'HR' | 'IT' | 'FINANCE' | 'ADMIN';
export type EmploymentStatus = 'ACTIVE' | 'OFFBOARDING' | 'EXITED';
export type EmploymentType = 'FULL_TIME' | 'PART_TIME' | 'CONTRACT' | 'INTERN';
export type Gender = 'MALE' | 'FEMALE' | 'OTHER' | 'PREFER_NOT_TO_SAY';

export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_active: boolean;
  date_joined?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface Department {
  id: number;
  name: string;
  code: string;
  description: string;
  head: number | null;
  head_name: string | null;
  is_active: boolean;
  employee_count: number;
  created_at: string;
  updated_at: string;
}

export interface Designation {
  id: number;
  name: string;
  code: string;
  description: string;
  department: number | null;
  department_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ManagerBrief {
  id: number;
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  designation_name: string;
  department_name: string;
}

export interface EmployeeListItem {
  id: number;
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  department: Department | null;
  designation_name: string;
  manager_id: number | null;
  manager_name: string | null;
  joining_date: string;
  employment_type: EmploymentType;
  employment_status: EmploymentStatus;
  location: string;
}

export interface Employee {
  id: number;
  employee_id: string;
  user: User;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  profile_photo: string | null;
  date_of_birth: string | null;
  gender: Gender | '';
  department: Department | null;
  designation: Designation | null;
  manager: ManagerBrief | null;
  joining_date: string;
  employment_status: EmploymentStatus;
  employment_type: EmploymentType;
  location: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  aadhaar_number: string;
  pan_number: string;
  uan_number: string;
  esi_number: string;
  bank_name: string;
  bank_account_holder_name: string;
  bank_account_number: string;
  bank_ifsc_code: string;
  direct_reports_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  message: string;
  detail?: string;
  errors?: Record<string, string[]>;
}

export type ResignationStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'MANAGER_REVIEW'
  | 'HR_REVIEW'
  | 'APPROVED'
  | 'NOTICE_PERIOD'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELLED';

export type NoticePeriodStatus = 'ACTIVE' | 'EARLY_RELEASE_REQUESTED' | 'COMPLETED';

export interface NoticePeriod {
  id: number;
  status: NoticePeriodStatus;
  status_display: string;
  notice_period_start_date: string | null;
  notice_period_days: number | null;
  expected_last_working_day: string | null;
  actual_last_working_day: string | null;
  notice_comments: string;
  early_release_requested_by_name: string | null;
  early_release_requested_at: string | null;
  early_release_request_reason: string;
  early_release_date: string | null;
  early_release_approved: boolean | null;
  early_release_reviewed_by_name: string | null;
  early_release_reviewed_at: string | null;
  early_release_review_notes: string;
  notice_extension_date: string | null;
  extension_reason: string;
  extension_recorded_by_name: string | null;
  extension_recorded_at: string | null;
  completed_by_name: string | null;
  completed_at: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export type ResignationReason =
  | 'BETTER_OPPORTUNITY'
  | 'PERSONAL_REASONS'
  | 'HIGHER_EDUCATION'
  | 'RELOCATION'
  | 'HEALTH_REASONS'
  | 'FAMILY_COMMITMENT'
  | 'CAREER_CHANGE'
  | 'COMPENSATION'
  | 'WORK_ENVIRONMENT'
  | 'OTHER';

export interface ResignationListItem {
  id: number;
  employee_id: string;
  employee_user_id: number;
  employee_name: string;
  department_name: string;
  status: ResignationStatus;
  status_display: string;
  reason: ResignationReason;
  reason_display: string;
  resignation_date: string;
  last_working_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResignationRequest {
  id: number;
  employee_id: string;
  employee_user_id: number;
  employee_name: string;
  employee_email: string;
  department_name: string;
  designation_name: string;
  manager_name: string | null;
  status: ResignationStatus;
  status_display: string;
  reason: ResignationReason;
  reason_display: string;
  resignation_date: string;
  last_working_date: string | null;
  /** Policy-derived notice duration: 1 month (tenure < 6 months) or 2 months. */
  notice_policy_months: number;
  notes: string;
  submitted_by_name: string | null;
  manager_reviewed_by_name: string | null;
  manager_reviewed_at: string | null;
  manager_notes: string;
  hr_reviewed_by_name: string | null;
  hr_reviewed_at: string | null;
  hr_notes: string;
  rejection_reason: string;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: number;
  notification_type: string;
  title: string;
  message: string;
  is_read: boolean;
  related_object_type: string;
  related_object_id: number | null;
  created_at: string;
}

// ─── Phase 5: Knowledge Transfer ─────────────────────────────────────────────

export type KTStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'SUBMITTED'
  | 'RECEIVER_REVIEW'
  | 'MANAGER_REVIEW'
  | 'COMPLETED'
  | 'REJECTED';

export type KTPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Project {
  id: number;
  name: string;
  code: string;
  description: string;
  department: number | null;
  department_name: string;
  manager: number | null;
  manager_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface KTDocument {
  id: number;
  url: string;
  description: string;
  added_by_name: string | null;
  created_at: string;
}

export interface KTListItem {
  id: number;
  title: string;
  project: number | null;
  project_name: string;
  responsibility: string;
  assigned_to: number;
  assigned_to_name: string | null;
  receiver: number;
  receiver_name: string | null;
  priority: KTPriority;
  priority_display: string;
  status: KTStatus;
  status_display: string;
  start_date: string | null;
  target_completion_date: string | null;
  completed_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeTransfer extends KTListItem {
  offboarding_request: number;
  description: string;
  project_detail: Project | null;
  assigned_to_user_id: number;
  receiver_user_id: number;
  completion_notes: string;
  receiver_comments: string;
  manager_comments: string;
  submitted_at: string | null;
  receiver_reviewed_by_name: string | null;
  receiver_reviewed_at: string | null;
  manager_reviewed_by_name: string | null;
  manager_reviewed_at: string | null;
  created_by_name: string | null;
  documents: KTDocument[];
}

export interface KTSummary {
  total: number;
  pending: number;
  in_progress: number;
  submitted: number;
  receiver_review: number;
  manager_review: number;
  completed: number;
  rejected: number;
  kt_phase_completed: boolean;
  kt_phase_completed_at: string | null;
}

// ─── Phase 6: Asset & Department Clearance ───────────────────────────────────

export type AssetType =
  | 'LAPTOP' | 'DESKTOP' | 'MONITOR' | 'MOBILE' | 'TABLET' | 'KEYBOARD'
  | 'MOUSE' | 'HEADSET' | 'ID_CARD' | 'ACCESS_CARD' | 'SIM_CARD' | 'OTHER';

export type AssetStatus =
  | 'ASSIGNED' | 'RETURN_PENDING' | 'RETURNED' | 'LOST' | 'DAMAGED' | 'CLEARED';

export type AssetCondition = 'GOOD' | 'FAIR' | 'DAMAGED' | 'NON_FUNCTIONAL';

export type AssetClearanceStatus =
  | 'RETURN_PENDING' | 'RETURNED' | 'CLEARED' | 'DAMAGED' | 'LOST' | 'REJECTED';

export type ClearanceDepartment = 'IT' | 'ADMIN' | 'FINANCE' | 'HR' | 'MANAGER';

export type DepartmentClearanceStatus =
  | 'PENDING' | 'IN_PROGRESS' | 'CLEARED' | 'REJECTED' | 'NOT_APPLICABLE';

export type ChecklistStatus = 'PENDING' | 'COMPLETED' | 'NOT_APPLICABLE';

export interface Asset {
  id: number;
  asset_id: string;
  asset_type: AssetType;
  asset_type_display: string;
  asset_name: string;
  serial_number: string;
  description: string;
  assigned_to: number | null;
  assigned_to_name: string | null;
  assigned_to_employee_id: string | null;
  assigned_date: string | null;
  status: AssetStatus;
  status_display: string;
  condition: AssetCondition | '';
  condition_display: string;
  remarks: string;
  created_at: string;
  updated_at: string;
}

export interface AssetClearance {
  id: number;
  offboarding_request: number;
  asset: number;
  asset_detail: Asset;
  asset_name: string;
  asset_code: string;
  serial_number: string;
  employee: number;
  employee_name: string | null;
  status: AssetClearanceStatus;
  status_display: string;
  return_date: string | null;
  condition_at_return: AssetCondition | '';
  condition_display: string;
  remarks: string;
  verified_by_name: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChecklistItem {
  id: number;
  department_clearance: number;
  title: string;
  description: string;
  status: ChecklistStatus;
  status_display: string;
  completed_by_name: string | null;
  completed_at: string | null;
  comments: string;
  created_at: string;
}

export interface DepartmentClearance {
  id: number;
  offboarding_request: number;
  department: ClearanceDepartment;
  department_display: string;
  assigned_to: number | null;
  assigned_to_name: string | null;
  status: DepartmentClearanceStatus;
  status_display: string;
  comments: string;
  clearance_date: string | null;
  cleared_by_name: string | null;
  cleared_at: string | null;
  created_at: string;
  updated_at: string;
  checklist_items: ChecklistItem[];
}

export interface ClearanceSummary {
  departments: {
    total: number; cleared: number; pending: number;
    in_progress: number; rejected: number; not_applicable: number;
  };
  assets: {
    total: number; returned: number; pending: number;
    cleared: number; damaged: number; lost: number; rejected: number;
  };
  clearance_completed: boolean;
  clearance_completed_at: string | null;
  asset_declaration_submitted: boolean;
  asset_declaration_at: string | null;
  asset_declaration_by_name: string | null;
  asset_declaration_notes: string;
}

// ─── Phase 7: Final Settlement & Exit Interview ──────────────────────────────

export type SettlementStatus = 'DRAFT' | 'PREPARED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';

export interface FinalSettlement {
  id: number;
  offboarding_request: number;
  employee: number;
  employee_name: string | null;
  pending_salary: string;
  leave_encashment: string;
  bonus: string;
  incentives: string;
  other_additions: string;
  notice_recovery: string;
  loan_deduction: string;
  advance_deduction: string;
  other_deductions: string;
  gross_amount: string;
  total_deductions: string;
  net_settlement: string;
  settlement_status: SettlementStatus;
  status_display: string;
  prepared_by_name: string | null;
  reviewed_by_name: string | null;
  approved_by_name: string | null;
  settlement_date: string | null;
  comments: string;
  created_at: string;
  updated_at: string;
}

/** Restricted view returned to the offboarding employee. */
export interface FinalSettlementEmployeeView {
  id: number;
  gross_amount: string;
  total_deductions: string;
  net_settlement: string;
  settlement_status: SettlementStatus;
  status_display: string;
  settlement_date: string | null;
}

export type ExitInterviewStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'REVIEWED';

export type ExitInterviewReason =
  | 'CAREER_GROWTH' | 'NEW_OPPORTUNITY' | 'HIGHER_STUDIES' | 'PERSONAL_REASONS'
  | 'RELOCATION' | 'COMPENSATION' | 'WORK_ENVIRONMENT' | 'MANAGEMENT'
  | 'ROLE_CHANGE' | 'OTHER';

export interface ExitInterview {
  id: number;
  offboarding_request: number;
  employee: number;
  employee_name: string | null;
  interview_date: string | null;
  conducted_by: number | null;
  conducted_by_name: string | null;
  primary_reason: ExitInterviewReason | '';
  secondary_reason: ExitInterviewReason | '';
  overall_experience: number;
  manager_feedback: number;
  work_environment_feedback: number;
  role_feedback: number;
  growth_feedback: number;
  compensation_feedback: number;
  what_went_well: string;
  what_could_improve: string;
  suggestions: string;
  additional_comments: string;
  would_recommend: boolean | null;
  would_rejoin: boolean | null;
  status: ExitInterviewStatus;
  status_display: string;
  hr_review_notes: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExitInterviewAnalytics {
  total_interviews: number;
  top_leaving_reasons: Record<string, number>;
  overall_experience_distribution: Record<string, number>;
  would_recommend: { yes: number; no: number };
  would_rejoin: { yes: number; no: number };
}

// ─── Phase 8: HR Dashboard & Final Review ────────────────────────────────────

export type FinalReviewStatus = 'NOT_READY' | 'READY_FOR_REVIEW' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED';

export type SectionStatus = 'COMPLETE' | 'IN_PROGRESS' | 'REJECTED' | 'PENDING' | 'NOT_APPLICABLE';

export interface OffboardingSummary {
  id: number;
  employee_name: string;
  employee_id: string;
  department_name: string;
  resignation_status: string;
  resignation_status_display: string;
  resignation_date: string | null;
  expected_last_working_day: string | null;
  sections: {
    resignation: SectionStatus;
    notice_period: SectionStatus;
    knowledge_transfer: SectionStatus;
    assets: SectionStatus;
    department_clearance: SectionStatus;
    settlement: SectionStatus;
    exit_interview: SectionStatus;
  };
  pending_items: string[];
  is_ready: boolean;
  final_review_status: FinalReviewStatus;
  final_review_status_display: string;
  final_reviewed_by_name: string | null;
  final_review_date: string | null;
  final_approval_date: string | null;
  final_review_comments: string;
  final_rejection_reason: string;
  settlement_status: string | null;
  exit_interview_status: string | null;
}

export interface HRDashboardData {
  summary: {
    total_offboarding: number;
    pending_manager_review: number;
    pending_hr_review: number;
    notice_period: number;
    kt_in_progress: number;
    clearance_pending: number;
    settlement_pending: number;
    exit_interview_pending: number;
    ready_for_final_review: number;
    under_final_review: number;
    completed: number;
  };
  pipeline: {
    resignation: number;
    notice: number;
    kt: number;
    clearance: number;
    settlement: number;
    exit_interview: number;
    final_review: number;
    completed: number;
  };
}

export interface HROffboardingRow {
  id: number;
  employee_name: string;
  employee_id: string;
  department_name: string;
  manager_name: string | null;
  current_stage: string;
  resignation_date: string | null;
  expected_last_working_day: string | null;
  kt_status: SectionStatus;
  clearance_status: SectionStatus;
  settlement_status: string;
  exit_interview_status: string;
  final_review_status: FinalReviewStatus;
  is_ready: boolean;
}

// ─── Phase 9: Exit Documents & Notifications ─────────────────────────────────

export type DocumentType =
  | 'RELIEVING_LETTER' | 'EXPERIENCE_LETTER' | 'FULL_FINAL_SETTLEMENT'
  | 'EXIT_CLEARANCE' | 'OTHER';

export type DocumentStatus =
  | 'DRAFT' | 'GENERATED' | 'UNDER_REVIEW' | 'APPROVED' | 'RELEASED' | 'REVOKED';

export interface OffboardingDocument {
  id: number;
  offboarding_request: number;
  employee: number;
  employee_name: string | null;
  document_type: DocumentType;
  document_type_display: string;
  document_number: string;
  document_title: string;
  status: DocumentStatus;
  status_display: string;
  version: number;
  document_date: string | null;
  prepared_by_name: string | null;
  reviewed_by_name: string | null;
  released_by_name: string | null;
  rejection_reason: string;
  revocation_reason: string;
  download_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyProfile {
  id: number;
  name: string;
  address: string;
  email: string;
  phone: string;
  logo: string | null;
  signatory_name: string;
  signatory_designation: string;
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: number;
  notification_type: string;
  type_display: string;
  title: string;
  message: string;
  is_read: boolean;
  related_object_type: string;
  related_object_id: number | null;
  related_offboarding: number | null;
  created_at: string;
  read_at: string | null;
}

export interface EmployeeFilters {
  search?: string;
  department?: number | string;
  designation?: number | string;
  employment_type?: string;
  status?: string;
  manager?: number | string;
  location?: string;
  ordering?: string;
  page?: number;
  page_size?: number;
}
