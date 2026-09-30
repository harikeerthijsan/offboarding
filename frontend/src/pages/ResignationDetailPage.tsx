import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { noticePeriodService } from '../services/noticePeriodService';
import type { NoticePeriod, ResignationRequest, ResignationStatus } from '../types';

const STATUS_LABEL: Record<ResignationStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  MANAGER_REVIEW: 'Manager Review',
  HR_REVIEW: 'HR Review',
  APPROVED: 'Approved',
  NOTICE_PERIOD: 'Notice Period',
  COMPLETED: 'Completed',
  REJECTED: 'Rejected',
  CANCELLED: 'Cancelled',
};

const STATUS_CLASS: Record<ResignationStatus, string> = {
  DRAFT: 'badge-secondary',
  SUBMITTED: 'badge-manager',
  MANAGER_REVIEW: 'badge-it',
  HR_REVIEW: 'badge-employee',
  APPROVED: 'badge-active',
  NOTICE_PERIOD: 'badge-it',
  COMPLETED: 'badge-active',
  REJECTED: 'badge-exited',
  CANCELLED: 'badge-offboarding',
};

const TIMELINE_STEPS: { status: ResignationStatus; label: string }[] = [
  { status: 'SUBMITTED', label: 'Submitted' },
  { status: 'MANAGER_REVIEW', label: 'Manager Approved' },
  { status: 'APPROVED', label: 'HR Approved' },
  { status: 'NOTICE_PERIOD', label: 'Notice Period' },
  { status: 'COMPLETED', label: 'Completed' },
];

function formatDate(d: string | null) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return d; }
}

function formatDateTime(d: string | null) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return d; }
}

function getTimelineState(status: ResignationStatus): number {
  const order: ResignationStatus[] = ['DRAFT', 'SUBMITTED', 'MANAGER_REVIEW', 'APPROVED', 'NOTICE_PERIOD', 'COMPLETED'];
  return order.indexOf(status);
}

interface ActionModalProps {
  title: string;
  action: 'approve' | 'reject' | 'cancel';
  onConfirm: (notes: string) => void;
  onClose: () => void;
  submitting: boolean;
  notesLabel?: string;
}

function ActionModal({ title, action, onConfirm, onClose, submitting, notesLabel = 'Notes' }: ActionModalProps) {
  const [notes, setNotes] = useState('');
  const isCancel = action === 'cancel';
  const isReject = action === 'reject';
  const notesRequired = isReject;
  const confirmLabel = isCancel ? 'Confirm Cancel' : isReject ? 'Confirm Reject' : 'Confirm Approve';
  const placeholder = isCancel ? 'Reason for cancellation (optional)…' : isReject ? 'Please provide a reason for rejection…' : 'Any comments…';
  return (
    <div className="modal-overlay" onClick={() => !submitting && onClose()}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <div className="modal-header">
          <h3>{title}</h3>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">
              {notesLabel} {notesRequired ? <span style={{ color: 'var(--danger)' }}>*</span> : '(optional)'}
            </label>
            <textarea
              className="form-input"
              rows={3}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder={placeholder}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={submitting}>
            Back
          </button>
          <button
            className={`btn ${action === 'approve' ? 'btn-primary' : 'btn-danger'}`}
            onClick={() => onConfirm(notes)}
            disabled={submitting || (notesRequired && !notes.trim())}
          >
            {submitting
              ? <><span className="btn-spinner" /> Processing…</>
              : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ResignationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [notice, setNotice] = useState<NoticePeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [modal, setModal] = useState<'manager-approve' | 'manager-reject' | 'hr-approve' | 'hr-reject' | 'cancel' | 'early-release' | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [earlyReleaseReason, setEarlyReleaseReason] = useState('');
  const [earlyReleaseMsg, setEarlyReleaseMsg] = useState('');

  useEffect(() => {
    if (!id) return;
    offboardingService.getResignation(Number(id))
      .then(res => {
        setResignation(res);
        if (['NOTICE_PERIOD', 'COMPLETED'].includes(res.status)) {
          noticePeriodService.get(Number(id)).then(setNotice).catch(() => setNotice(null));
        }
      })
      .catch(() => setError('Failed to load resignation details.'))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleEarlyReleaseRequest() {
    if (!resignation) return;
    setSubmitting(true);
    setActionError('');
    setEarlyReleaseMsg('');
    try {
      const np = await noticePeriodService.requestEarlyRelease(resignation.id, earlyReleaseReason);
      setNotice(np);
      setModal(null);
      setEarlyReleaseReason('');
      setEarlyReleaseMsg('Your early release request has been submitted to HR.');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string; reason?: string[] }; status?: number } };
      setActionError(e?.response?.data?.detail || e?.response?.data?.reason?.[0] || 'Failed to submit early release request.');
      setModal(null);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAction(notes: string) {
    if (!resignation || !modal) return;
    setSubmitting(true);
    setActionError('');
    try {
      let updated: ResignationRequest;
      if (modal === 'manager-approve') {
        updated = await offboardingService.managerAction(resignation.id, 'approve', notes);
      } else if (modal === 'manager-reject') {
        updated = await offboardingService.managerAction(resignation.id, 'reject', notes);
      } else if (modal === 'hr-approve') {
        updated = await offboardingService.hrAction(resignation.id, 'approve', notes);
      } else if (modal === 'hr-reject') {
        updated = await offboardingService.hrAction(resignation.id, 'reject', notes);
      } else {
        updated = await offboardingService.cancelResignation(resignation.id, notes);
      }
      setResignation(updated);
      setModal(null);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string }; status?: number } };
      const detail = e?.response?.data?.detail;
      const httpStatus = e?.response?.status;
      const message = httpStatus === 403
        ? (detail || 'You do not have permission to perform this action.')
        : (detail || 'Action failed. Please try again.');
      setActionError(message);
      setModal(null);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  const isManager = user?.role === 'MANAGER' || user?.role === 'ADMIN';
  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';

  const canManagerApprove = isManager && resignation.status === 'SUBMITTED';
  const canHRApprove = isHR && resignation.status === 'MANAGER_REVIEW';
  const canCancel = (user?.role === 'EMPLOYEE' || user?.role === 'MANAGER' || user?.role === 'HR' || user?.role === 'ADMIN') &&
    ['DRAFT', 'SUBMITTED'].includes(resignation.status);

  const timelineStep = getTimelineState(resignation.status);
  const isTerminal = ['COMPLETED', 'REJECTED', 'CANCELLED'].includes(resignation.status);

  // HR can manage notice period once approved or during notice period
  const canManageNotice = isHR && ['APPROVED', 'NOTICE_PERIOD'].includes(resignation.status);
  // Knowledge transfer is available once the offboarding is approved (and after)
  const showKnowledgeTransfer = ['APPROVED', 'NOTICE_PERIOD', 'COMPLETED'].includes(resignation.status);
  // Employee (owner) can request early release during an active notice period
  const canRequestEarlyRelease =
    user?.role === 'EMPLOYEE' &&
    resignation.status === 'NOTICE_PERIOD' &&
    (!notice || notice.status === 'ACTIVE');

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate('/offboarding')} style={{ marginBottom: 8 }}>
            ← Back
          </button>
          <h1 className="page-title">Resignation Request #{resignation.id}</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        <span className={`badge ${STATUS_CLASS[resignation.status]}`} style={{ fontSize: 14, padding: '6px 14px' }}>
          {STATUS_LABEL[resignation.status]}
        </span>
      </div>

      {actionError && (
        <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>
      )}
      {earlyReleaseMsg && (
        <div className="alert" style={{ marginBottom: 16, background: 'var(--success-bg, #ecfdf5)', color: 'var(--success, #047857)' }}>
          {earlyReleaseMsg}
        </div>
      )}

      {/* Knowledge transfer entry point */}
      {showKnowledgeTransfer && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              Manage the knowledge transfer and handover tasks for this offboarding.
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/knowledge-transfer`)}>
              Knowledge Transfer
            </button>
          </div>
        </div>
      )}

      {/* Clearance entry point */}
      {showKnowledgeTransfer && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              Track asset returns and department clearances for this offboarding.
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/clearance`)}>
              Clearance
            </button>
          </div>
        </div>
      )}

      {/* Final settlement entry point */}
      {showKnowledgeTransfer && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              Prepare and review the employee's full & final settlement.
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/settlement`)}>
              Final Settlement
            </button>
          </div>
        </div>
      )}

      {/* Exit interview entry point */}
      {showKnowledgeTransfer && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              Complete or review the exit interview and feedback.
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/exit-interview`)}>
              Exit Interview
            </button>
          </div>
        </div>
      )}

      {/* Final review entry point (HR) */}
      {showKnowledgeTransfer && isHR && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              Run the final HR review and approve the offboarding once all items are complete.
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/final-review`)}>
              Final Review
            </button>
          </div>
        </div>
      )}

      {/* Exit documents entry point */}
      {showKnowledgeTransfer && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              {isHR ? 'Generate, review and release exit documents (relieving/experience letters, settlement, clearance).'
                    : 'View and download your released exit documents.'}
            </span>
            <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/documents`)}>
              Exit Documents
            </button>
          </div>
        </div>
      )}

      {/* Notice period actions */}
      {(canManageNotice || canRequestEarlyRelease) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              {canManageNotice && resignation.status === 'APPROVED' && 'This resignation is approved. Start and manage the notice period.'}
              {canManageNotice && resignation.status === 'NOTICE_PERIOD' && 'Manage the ongoing notice period, extensions, and completion.'}
              {canRequestEarlyRelease && 'You are currently serving your notice period. You may request an early release.'}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              {canRequestEarlyRelease && (
                <button className="btn btn-secondary" onClick={() => setModal('early-release')}>
                  Request Early Release
                </button>
              )}
              {canManageNotice && (
                <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${resignation.id}/notice-period`)}>
                  Manage Notice Period
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!isTerminal && (canManagerApprove || canHRApprove || canCancel) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 14, flex: 1 }}>
              {canManagerApprove && 'This resignation is awaiting your review.'}
              {canHRApprove && 'This resignation has been approved by the manager and is awaiting HR review.'}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              {canCancel && (
                <button className="btn btn-secondary" onClick={() => setModal('cancel')}>
                  Cancel Request
                </button>
              )}
              {canManagerApprove && (
                <>
                  <button className="btn btn-danger" onClick={() => setModal('manager-reject')}>
                    Reject
                  </button>
                  <button className="btn btn-primary" onClick={() => setModal('manager-approve')}>
                    Approve
                  </button>
                </>
              )}
              {canHRApprove && (
                <>
                  <button className="btn btn-danger" onClick={() => setModal('hr-reject')}>
                    Reject
                  </button>
                  <button className="btn btn-primary" onClick={() => setModal('hr-approve')}>
                    Approve
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      {!['REJECTED', 'CANCELLED'].includes(resignation.status) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 20, fontSize: 15, fontWeight: 600 }}>Progress</h3>
          <div className="timeline-steps">
            {TIMELINE_STEPS.map((step, idx) => {
              const stepOrder = idx + 1; // matches getTimelineState order index
              const done = timelineStep > stepOrder;
              const active = timelineStep === stepOrder;
              return (
                <div key={step.status} className={`timeline-step ${done ? 'done' : active ? 'active' : ''}`}>
                  <div className="timeline-dot">{done ? '✓' : idx + 1}</div>
                  <span className="timeline-label">{step.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>Employee Details</h3>
          <div>
            <div className="detail-row"><span className="detail-label">Name</span><span className="detail-value">{resignation.employee_name}</span></div>
            <div className="detail-row"><span className="detail-label">Employee ID</span><span className="detail-value">{resignation.employee_id}</span></div>
            <div className="detail-row"><span className="detail-label">Email</span><span className="detail-value">{resignation.employee_email}</span></div>
            <div className="detail-row"><span className="detail-label">Department</span><span className="detail-value">{resignation.department_name || '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Designation</span><span className="detail-value">{resignation.designation_name || '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Manager</span><span className="detail-value">{resignation.manager_name || '—'}</span></div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>Resignation Details</h3>
          <div>
            <div className="detail-row"><span className="detail-label">Reason</span><span className="detail-value">{resignation.reason_display}</span></div>
            <div className="detail-row"><span className="detail-label">Resignation Date</span><span className="detail-value">{formatDate(resignation.resignation_date)}</span></div>
            <div className="detail-row"><span className="detail-label">Last Working Date</span><span className="detail-value">{formatDate(resignation.last_working_date)}</span></div>
            <div className="detail-row"><span className="detail-label">Submitted By</span><span className="detail-value">{resignation.submitted_by_name || '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Submitted On</span><span className="detail-value">{formatDate(resignation.created_at)}</span></div>
            {resignation.notes && (
              <div className="detail-row" style={{ flexDirection: 'column', gap: 4 }}>
                <span className="detail-label">Notes</span>
                <span className="detail-value" style={{ marginLeft: 0, whiteSpace: 'pre-wrap' }}>{resignation.notes}</span>
              </div>
            )}
          </div>
        </div>

        {resignation.manager_reviewed_by_name && (
          <div className="card">
            <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>Manager Review</h3>
            <div>
              <div className="detail-row"><span className="detail-label">Reviewed By</span><span className="detail-value">{resignation.manager_reviewed_by_name}</span></div>
              <div className="detail-row"><span className="detail-label">Reviewed At</span><span className="detail-value">{formatDateTime(resignation.manager_reviewed_at)}</span></div>
              {resignation.manager_notes && (
                <div className="detail-row"><span className="detail-label">Resignation Discussion Summary</span><span className="detail-value">{resignation.manager_notes}</span></div>
              )}
            </div>
          </div>
        )}

        {resignation.hr_reviewed_by_name && (
          <div className="card">
            <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>HR Review</h3>
            <div>
              <div className="detail-row"><span className="detail-label">Reviewed By</span><span className="detail-value">{resignation.hr_reviewed_by_name}</span></div>
              <div className="detail-row"><span className="detail-label">Reviewed At</span><span className="detail-value">{formatDateTime(resignation.hr_reviewed_at)}</span></div>
              {resignation.hr_notes && (
                <div className="detail-row"><span className="detail-label">Notes</span><span className="detail-value">{resignation.hr_notes}</span></div>
              )}
            </div>
          </div>
        )}

        {resignation.rejection_reason && ['REJECTED', 'CANCELLED'].includes(resignation.status) && (
          <div className="card">
            <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600, color: 'var(--danger)' }}>
              {resignation.status === 'CANCELLED' ? 'Cancellation Reason' : 'Rejection Reason'}
            </h3>
            <p style={{ color: 'var(--text-secondary)' }}>{resignation.rejection_reason}</p>
          </div>
        )}
      </div>

      {/* Notice Period (read-only) */}
      {notice && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>Notice Period</h3>
            <span className="badge badge-it">{notice.status_display}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
            <div className="detail-row"><span className="detail-label">Start Date</span><span className="detail-value">{formatDate(notice.notice_period_start_date)}</span></div>
            <div className="detail-row"><span className="detail-label">Notice Period Days</span><span className="detail-value">{notice.notice_period_days ?? '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Expected Last Working Day</span><span className="detail-value">{formatDate(notice.expected_last_working_day)}</span></div>
            <div className="detail-row"><span className="detail-label">Actual Last Working Day</span><span className="detail-value">{formatDate(notice.actual_last_working_day)}</span></div>
            {notice.notice_extension_date && (
              <div className="detail-row"><span className="detail-label">Extended To</span><span className="detail-value">{formatDate(notice.notice_extension_date)}</span></div>
            )}
            {notice.early_release_date && (
              <div className="detail-row"><span className="detail-label">Early Release Date</span><span className="detail-value">{formatDate(notice.early_release_date)}</span></div>
            )}
          </div>
          {notice.notice_comments && (
            <div className="detail-row" style={{ flexDirection: 'column', gap: 4 }}>
              <span className="detail-label">Comments</span>
              <span className="detail-value" style={{ marginLeft: 0, whiteSpace: 'pre-wrap' }}>{notice.notice_comments}</span>
            </div>
          )}
          {notice.status === 'EARLY_RELEASE_REQUESTED' && (
            <div className="alert alert-warning" style={{ marginTop: 12 }}>
              An early release request is pending HR review.
              {notice.early_release_request_reason && <> Reason: {notice.early_release_request_reason}</>}
            </div>
          )}
          {notice.early_release_reviewed_by_name && notice.early_release_approved != null && (
            <div className="detail-row" style={{ marginTop: 8 }}>
              <span className="detail-label">Early Release</span>
              <span className="detail-value">
                {notice.early_release_approved ? `Approved (${formatDate(notice.early_release_date)})` : 'Rejected'}
                {' · '}{notice.early_release_reviewed_by_name}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Early release request modal */}
      {modal === 'early-release' && (
        <div className="modal-overlay" onClick={() => !submitting && setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Request Early Release</h3></div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
                Explain why you are requesting to be released before your expected last working day.
                HR will review and set a release date if approved.
              </p>
              <div className="form-group">
                <label className="form-label">Reason <span style={{ color: 'var(--danger)' }}>*</span></label>
                <textarea className="form-input" rows={4} value={earlyReleaseReason}
                  onChange={e => setEarlyReleaseReason(e.target.value)}
                  placeholder="Reason for early release…" />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModal(null)} disabled={submitting}>Back</button>
              <button className="btn btn-primary" onClick={handleEarlyReleaseRequest}
                disabled={submitting || !earlyReleaseReason.trim()}>
                {submitting ? <><span className="btn-spinner" /> Submitting…</> : 'Submit Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      {modal === 'manager-approve' && (
        <ActionModal
          title="Approve Resignation"
          action="approve"
          notesLabel="Resignation Discussion Summary"
          onConfirm={handleAction}
          onClose={() => setModal(null)}
          submitting={submitting}
        />
      )}
      {modal === 'manager-reject' && (
        <ActionModal
          title="Reject Resignation"
          action="reject"
          notesLabel="Resignation Discussion Summary"
          onConfirm={handleAction}
          onClose={() => setModal(null)}
          submitting={submitting}
        />
      )}
      {modal === 'hr-approve' && (
        <ActionModal
          title="Approve Resignation (HR)"
          action="approve"
          onConfirm={handleAction}
          onClose={() => setModal(null)}
          submitting={submitting}
        />
      )}
      {modal === 'hr-reject' && (
        <ActionModal
          title="Reject Resignation (HR)"
          action="reject"
          onConfirm={handleAction}
          onClose={() => setModal(null)}
          submitting={submitting}
        />
      )}
      {modal === 'cancel' && (
        <ActionModal
          title="Cancel Resignation Request"
          action="cancel"
          onConfirm={handleAction}
          onClose={() => setModal(null)}
          submitting={submitting}
        />
      )}
    </div>
  );
}
