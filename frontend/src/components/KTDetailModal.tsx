import { useEffect, useState } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import { ktService } from '../services/ktService';
import type { KnowledgeTransfer } from '../types';
import { KT_STATUS_BADGE, KT_PRIORITY_BADGE, formatDate, formatDateTime, ktErrorMessage } from '../utils/kt';

interface Props {
  ktId: number;
  onClose: () => void;
  onChanged?: () => void;
}

export default function KTDetailModal({ ktId, onClose, onChanged }: Props) {
  const { user } = useAuthContext();
  const [kt, setKt] = useState<KnowledgeTransfer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  // Inline editors
  const [notes, setNotes] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);
  const [docUrl, setDocUrl] = useState('');
  const [docDesc, setDocDesc] = useState('');

  // Sub-forms
  const [showReceiverReject, setShowReceiverReject] = useState(false);
  const [showManagerApprove, setShowManagerApprove] = useState(false);
  const [showManagerReject, setShowManagerReject] = useState(false);
  const [comments, setComments] = useState('');
  const [completedDate, setCompletedDate] = useState('');

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [ktId]);

  async function load() {
    setLoading(true);
    try {
      const data = await ktService.get(ktId);
      setKt(data);
      setNotes(data.completion_notes || '');
    } catch {
      setError('Failed to load knowledge transfer.');
    } finally {
      setLoading(false);
    }
  }

  async function run(fn: () => Promise<unknown>, resetForms = true) {
    setBusy(true); setActionError('');
    try {
      await fn();
      await load();
      if (resetForms) {
        setShowReceiverReject(false); setShowManagerApprove(false);
        setShowManagerReject(false); setComments(''); setCompletedDate('');
        setEditingNotes(false); setDocUrl(''); setDocDesc('');
      }
      onChanged?.();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Action failed.'));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
        </div>
      </div>
    );
  }
  if (error || !kt) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
          <div className="modal-body"><div className="error-message">{error || 'Not found.'}</div></div>
          <div className="modal-footer"><button className="btn btn-secondary" onClick={onClose}>Close</button></div>
        </div>
      </div>
    );
  }

  const isAssigned = kt.assigned_to_user_id === user?.id;
  const isReceiver = kt.receiver_user_id === user?.id;
  const isManagerLike = user?.role === 'MANAGER' || user?.role === 'ADMIN';
  const isPrivileged = user?.role === 'HR' || user?.role === 'ADMIN' || user?.role === 'MANAGER';
  const editable = kt.status !== 'COMPLETED';

  const canStart = isAssigned && (kt.status === 'PENDING' || kt.status === 'REJECTED');
  const canSubmit = isAssigned && kt.status === 'IN_PROGRESS';
  const canEditNotes = isAssigned && ['PENDING', 'IN_PROGRESS', 'REJECTED'].includes(kt.status);
  const canReceiverReview = isReceiver && (kt.status === 'SUBMITTED' || kt.status === 'RECEIVER_REVIEW');
  const canManagerReview = isManagerLike && kt.status === 'MANAGER_REVIEW';
  const canAddDoc = editable && (isAssigned || isPrivileged);

  return (
    <div className="modal-overlay" onClick={() => !busy && onClose()}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>{kt.title}</h3>
          <span className={`badge ${KT_STATUS_BADGE[kt.status]}`}>{kt.status_display}</span>
        </div>

        <div className="modal-body" style={{ maxHeight: '65vh', overflowY: 'auto' }}>
          {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}

          {/* Overview */}
          <div className="kt-section">
            <h4>Overview</h4>
            <div className="detail-row"><span className="detail-label">Priority</span>
              <span className="detail-value"><span className={`badge ${KT_PRIORITY_BADGE[kt.priority]}`}>{kt.priority_display}</span></span></div>
            <div className="detail-row"><span className="detail-label">Employee (handing over)</span><span className="detail-value">{kt.assigned_to_name}</span></div>
            <div className="detail-row"><span className="detail-label">Receiver</span><span className="detail-value">{kt.receiver_name}</span></div>
          </div>

          {/* Project & responsibility */}
          <div className="kt-section">
            <h4>Project Information</h4>
            <div className="detail-row"><span className="detail-label">Project</span><span className="detail-value">{kt.project_name || '—'}</span></div>
            {kt.description && (
              <div className="detail-row" style={{ flexDirection: 'column', gap: 4 }}>
                <span className="detail-label">Description</span>
                <span className="detail-value" style={{ marginLeft: 0, whiteSpace: 'pre-wrap' }}>{kt.description}</span>
              </div>
            )}
            <div className="detail-row" style={{ flexDirection: 'column', gap: 4 }}>
              <span className="detail-label">Responsibility</span>
              <span className="detail-value" style={{ marginLeft: 0, whiteSpace: 'pre-wrap' }}>{kt.responsibility || '—'}</span>
            </div>
          </div>

          {/* Dates */}
          <div className="kt-section">
            <h4>Dates</h4>
            <div className="detail-row"><span className="detail-label">Start Date</span><span className="detail-value">{formatDate(kt.start_date)}</span></div>
            <div className="detail-row"><span className="detail-label">Target Completion</span><span className="detail-value">{formatDate(kt.target_completion_date)}</span></div>
            <div className="detail-row"><span className="detail-label">Completion Date</span><span className="detail-value">{formatDate(kt.completed_date)}</span></div>
          </div>

          {/* Handover / completion notes */}
          <div className="kt-section">
            <h4>Handover Details</h4>
            {editingNotes ? (
              <>
                <textarea className="form-input" rows={4} value={notes} onChange={e => setNotes(e.target.value)}
                  placeholder="Progress, handover details, documentation references…" />
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button className="btn btn-secondary" onClick={() => { setEditingNotes(false); setNotes(kt.completion_notes || ''); }} disabled={busy}>Cancel</button>
                  <button className="btn btn-primary" onClick={() => run(() => ktService.update(kt.id, { completion_notes: notes }))} disabled={busy}>Save Notes</button>
                </div>
              </>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span style={{ whiteSpace: 'pre-wrap', color: 'var(--text)' }}>{kt.completion_notes || <em style={{ color: 'var(--text-muted)' }}>No notes yet.</em>}</span>
                {canEditNotes && <button className="btn btn-ghost" onClick={() => setEditingNotes(true)}>Edit</button>}
              </div>
            )}
          </div>

          {/* Documents */}
          <div className="kt-section">
            <h4>Documentation References</h4>
            {kt.documents.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No documents added.</p>}
            {kt.documents.map(doc => (
              <div key={doc.id} className="kt-doc-row">
                <div style={{ minWidth: 0 }}>
                  <a href={doc.url} target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', wordBreak: 'break-all' }}>{doc.url}</a>
                  {doc.description && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{doc.description}</div>}
                </div>
                {canAddDoc && (
                  <button className="btn btn-ghost" onClick={() => run(() => ktService.deleteDocument(kt.id, doc.id))} disabled={busy}>Remove</button>
                )}
              </div>
            ))}
            {canAddDoc && (
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input className="form-input" style={{ flex: 2, minWidth: 180 }} placeholder="https://…" value={docUrl} onChange={e => setDocUrl(e.target.value)} />
                <input className="form-input" style={{ flex: 1, minWidth: 120 }} placeholder="Description" value={docDesc} onChange={e => setDocDesc(e.target.value)} />
                <button className="btn btn-secondary" disabled={busy || !docUrl.trim()}
                  onClick={() => run(() => ktService.addDocument(kt.id, docUrl, docDesc), false).then(() => { setDocUrl(''); setDocDesc(''); })}>
                  Add
                </button>
              </div>
            )}
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
              Do not include passwords, API keys, or secrets in documentation links.
            </p>
          </div>

          {/* Review history / comments */}
          {(kt.receiver_comments || kt.receiver_reviewed_by_name || kt.manager_comments || kt.manager_reviewed_by_name) && (
            <div className="kt-section">
              <h4>Review History</h4>
              {kt.submitted_at && (
                <div className="detail-row"><span className="detail-label">Submitted</span><span className="detail-value">{formatDateTime(kt.submitted_at)}</span></div>
              )}
              {kt.receiver_reviewed_by_name && (
                <>
                  <div className="detail-row"><span className="detail-label">Receiver Review</span><span className="detail-value">{kt.receiver_reviewed_by_name} · {formatDateTime(kt.receiver_reviewed_at)}</span></div>
                  {kt.receiver_comments && <div className="detail-row"><span className="detail-label">Receiver Comments</span><span className="detail-value">{kt.receiver_comments}</span></div>}
                </>
              )}
              {kt.manager_reviewed_by_name && (
                <>
                  <div className="detail-row"><span className="detail-label">Manager Review</span><span className="detail-value">{kt.manager_reviewed_by_name} · {formatDateTime(kt.manager_reviewed_at)}</span></div>
                  {kt.manager_comments && <div className="detail-row"><span className="detail-label">Manager Comments</span><span className="detail-value">{kt.manager_comments}</span></div>}
                </>
              )}
            </div>
          )}

          {/* Receiver reject form */}
          {showReceiverReject && (
            <div className="kt-section">
              <label className="form-label">Reason for requesting changes <span style={{ color: 'var(--danger)' }}>*</span></label>
              <textarea className="form-input" rows={3} value={comments} onChange={e => setComments(e.target.value)} placeholder="e.g. The deployment documentation is incomplete. Please add rollback instructions." />
            </div>
          )}
          {/* Manager approve form */}
          {showManagerApprove && (
            <div className="kt-section">
              <label className="form-label">Completion Date <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input type="date" className="form-input" value={completedDate} onChange={e => setCompletedDate(e.target.value)} />
              <label className="form-label" style={{ marginTop: 8 }}>Comments (optional)</label>
              <textarea className="form-input" rows={2} value={comments} onChange={e => setComments(e.target.value)} />
            </div>
          )}
          {/* Manager reject form */}
          {showManagerReject && (
            <div className="kt-section">
              <label className="form-label">Reason for requesting changes <span style={{ color: 'var(--danger)' }}>*</span></label>
              <textarea className="form-input" rows={3} value={comments} onChange={e => setComments(e.target.value)} />
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ flexWrap: 'wrap', gap: 8 }}>
          <button className="btn btn-secondary" onClick={onClose} disabled={busy}>Close</button>

          {canStart && (
            <button className="btn btn-primary" onClick={() => run(() => ktService.start(kt.id))} disabled={busy}>
              {kt.status === 'REJECTED' ? 'Resume Work' : 'Start KT'}
            </button>
          )}
          {canSubmit && (
            <button className="btn btn-primary"
              onClick={() => { if (confirm('Are you sure you want to submit this KT for review?\n\nAfter submission, the receiver will review the handover.')) run(() => ktService.submit(kt.id)); }}
              disabled={busy}>
              Submit for Review
            </button>
          )}

          {canReceiverReview && !showReceiverReject && (
            <>
              <button className="btn btn-danger" onClick={() => setShowReceiverReject(true)} disabled={busy}>Request Changes</button>
              <button className="btn btn-primary" onClick={() => run(() => ktService.receiverAction(kt.id, 'accept'))} disabled={busy}>Accept</button>
            </>
          )}
          {canReceiverReview && showReceiverReject && (
            <>
              <button className="btn btn-secondary" onClick={() => { setShowReceiverReject(false); setComments(''); }} disabled={busy}>Back</button>
              <button className="btn btn-danger" onClick={() => run(() => ktService.receiverAction(kt.id, 'request_changes', comments))} disabled={busy || !comments.trim()}>Send Request</button>
            </>
          )}

          {canManagerReview && !showManagerApprove && !showManagerReject && (
            <>
              <button className="btn btn-danger" onClick={() => setShowManagerReject(true)} disabled={busy}>Request Changes</button>
              <button className="btn btn-primary" onClick={() => setShowManagerApprove(true)} disabled={busy}>Approve</button>
            </>
          )}
          {canManagerReview && showManagerApprove && (
            <>
              <button className="btn btn-secondary" onClick={() => { setShowManagerApprove(false); setComments(''); setCompletedDate(''); }} disabled={busy}>Back</button>
              <button className="btn btn-primary" onClick={() => run(() => ktService.managerAction(kt.id, 'approve', { completed_date: completedDate, comments }))} disabled={busy || !completedDate}>Confirm Approval</button>
            </>
          )}
          {canManagerReview && showManagerReject && (
            <>
              <button className="btn btn-secondary" onClick={() => { setShowManagerReject(false); setComments(''); }} disabled={busy}>Back</button>
              <button className="btn btn-danger" onClick={() => run(() => ktService.managerAction(kt.id, 'request_changes', { comments }))} disabled={busy || !comments.trim()}>Send Request</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
