import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { hrOffboardingService } from '../services/hrOffboardingService';
import type { OffboardingSummary, SectionStatus } from '../types';
import { formatDate, ktErrorMessage } from '../utils/kt';
import {
  FINAL_REVIEW_BADGE, SECTION_ICON, SECTION_LABEL, sectionDotClass,
} from '../utils/finalReview';

const SECTIONS: { key: keyof OffboardingSummary['sections']; label: string }[] = [
  { key: 'resignation', label: 'Resignation Approved' },
  { key: 'notice_period', label: 'Notice Period Completed' },
  { key: 'knowledge_transfer', label: 'Knowledge Transfer Completed' },
  { key: 'assets', label: 'Assets Cleared' },
  { key: 'department_clearance', label: 'Department Clearance Completed' },
  { key: 'settlement', label: 'Final Settlement Approved' },
  { key: 'exit_interview', label: 'Exit Interview Completed' },
];

function SectionRow({ label, status }: { label: string; status: SectionStatus }) {
  return (
    <div className="fr-check-row">
      <span>{label}</span>
      <span className="sec-status">
        <span className={sectionDotClass(status)}>{SECTION_ICON[status]}</span>
        {SECTION_LABEL[status]}
      </span>
    </div>
  );
}

export default function FinalReviewPage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [sum, setSum] = useState<OffboardingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  const [reviewDate, setReviewDate] = useState('');
  const [showApprove, setShowApprove] = useState(false);
  const [approvalDate, setApprovalDate] = useState('');
  const [approveComments, setApproveComments] = useState('');

  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';

  const load = useCallback(async () => {
    try {
      setSum(await hrOffboardingService.summary(oid));
    } catch {
      setError('Failed to load the final review.');
    }
  }, [oid]);

  useEffect(() => { (async () => { setLoading(true); await load(); setLoading(false); })(); }, [load]);

  async function handleStart() {
    setBusy(true); setActionError('');
    try { await hrOffboardingService.startFinalReview(oid, reviewDate); setMsg('Final review started.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to start final review.')); }
    finally { setBusy(false); }
  }

  async function handleApprove() {
    setBusy(true); setActionError('');
    try {
      await hrOffboardingService.approveFinalReview(oid, approvalDate, approveComments);
      setShowApprove(false); setMsg('Offboarding finally approved.'); await load();
    } catch (err) { setActionError(ktErrorMessage(err, 'Failed to approve.')); }
    finally { setBusy(false); }
  }

  async function handleReject() {
    const reason = prompt('Why is this offboarding request being rejected?') || '';
    if (!reason.trim()) return;
    setBusy(true); setActionError('');
    try { await hrOffboardingService.rejectFinalReview(oid, reason); setMsg('Final review rejected.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to reject.')); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!sum) return null;

  const frs = sum.final_review_status;

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate('/hr/offboarding')} style={{ marginBottom: 8 }}>← Dashboard</button>
          <h1 className="page-title">Final Review</h1>
          <p className="page-subtitle">{sum.employee_name} · {sum.employee_id} · {sum.department_name}</p>
        </div>
        <span className={`badge ${FINAL_REVIEW_BADGE[frs]}`} style={{ fontSize: 14, padding: '6px 14px' }}>
          {sum.final_review_status_display}
        </span>
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      {/* Employee summary */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Employee Information</h3>
        <div className="detail-row"><span className="detail-label">Employee</span><span className="detail-value">{sum.employee_name} ({sum.employee_id})</span></div>
        <div className="detail-row"><span className="detail-label">Department</span><span className="detail-value">{sum.department_name || '—'}</span></div>
        <div className="detail-row"><span className="detail-label">Resignation Date</span><span className="detail-value">{formatDate(sum.resignation_date)}</span></div>
        <div className="detail-row"><span className="detail-label">Expected LWD</span><span className="detail-value">{sum.expected_last_working_day ? formatDate(sum.expected_last_working_day) : 'Not entered'}</span></div>
      </div>

      {/* Checklist */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Final Review Checklist</h3>
        {SECTIONS.map(s => <SectionRow key={s.key} label={s.label} status={sum.sections[s.key]} />)}
        {!sum.is_ready && (
          <div className="alert alert-warning" style={{ marginTop: 12 }}>
            Final approval is blocked. Pending: {sum.pending_items.join(', ')}
          </div>
        )}
      </div>

      {/* Existing final review info */}
      {(sum.final_review_date || sum.final_approval_date || sum.final_rejection_reason) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Review Record</h3>
          <div className="detail-row"><span className="detail-label">Reviewed By</span><span className="detail-value">{sum.final_reviewed_by_name || '—'}</span></div>
          <div className="detail-row"><span className="detail-label">Final Review Date</span><span className="detail-value">{sum.final_review_date ? formatDate(sum.final_review_date) : 'Not entered'}</span></div>
          <div className="detail-row"><span className="detail-label">Final Approval Date</span><span className="detail-value">{sum.final_approval_date ? formatDate(sum.final_approval_date) : 'Not entered'}</span></div>
          {sum.final_review_comments && <div className="detail-row"><span className="detail-label">Comments</span><span className="detail-value">{sum.final_review_comments}</span></div>}
          {sum.final_rejection_reason && <div className="detail-row"><span className="detail-label">Rejection Reason</span><span className="detail-value">{sum.final_rejection_reason}</span></div>}
        </div>
      )}

      {/* Actions */}
      {isHR && frs !== 'APPROVED' && (
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>HR Final Approval</h3>
          {frs !== 'UNDER_REVIEW' ? (
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Final Review Date <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={reviewDate} onChange={e => setReviewDate(e.target.value)} />
              </div>
              <button className="btn btn-primary" onClick={handleStart} disabled={busy || !sum.is_ready || !reviewDate}>
                Start Final Review
              </button>
              {!sum.is_ready && <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Complete all prerequisites first.</span>}
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-danger" onClick={handleReject} disabled={busy}>Reject Final Approval</button>
              <button className="btn btn-primary" onClick={() => setShowApprove(true)} disabled={busy}>Approve Offboarding</button>
            </div>
          )}
        </div>
      )}
      {frs === 'APPROVED' && (
        <div className="card"><span style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Offboarding finally approved on {formatDate(sum.final_approval_date)}</span></div>
      )}

      {/* Approve modal */}
      {showApprove && (
        <div className="modal-overlay" onClick={() => !busy && setShowApprove(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="modal-header"><h3>Confirm Final Approval</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
                You are about to approve the final offboarding request for <strong>{sum.employee_name}</strong> ({sum.employee_id}).
                All required clearance and settlement items are complete.
              </p>
              <div className="form-group">
                <label className="form-label">Final Approval Date <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={approvalDate} onChange={e => setApprovalDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Comments</label>
                <textarea className="form-input" rows={2} value={approveComments} onChange={e => setApproveComments(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowApprove(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleApprove} disabled={busy || !approvalDate}>Confirm Final Approval</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
