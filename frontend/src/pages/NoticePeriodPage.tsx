import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { noticePeriodService } from '../services/noticePeriodService';
import type { NoticePeriod, ResignationRequest } from '../types';

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

/** Add whole months to a YYYY-MM-DD date, clamping the day to the month's length. */
function addMonthsStr(dateStr: string, months: number): string {
  const d = new Date(dateStr + 'T00:00:00');
  if (Number.isNaN(d.getTime())) return '';
  const day = d.getDate();
  d.setMonth(d.getMonth() + months);
  if (d.getDate() < day) d.setDate(0);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: Record<string, unknown>; status?: number } };
  const data = e?.response?.data;
  if (data) {
    if (typeof data.detail === 'string') return data.detail;
    // Field errors — surface the first
    const firstKey = Object.keys(data)[0];
    if (firstKey) {
      const val = data[firstKey];
      if (Array.isArray(val)) return `${firstKey}: ${val[0]}`;
      if (typeof val === 'string') return `${firstKey}: ${val}`;
    }
  }
  return fallback;
}

export default function NoticePeriodPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [notice, setNotice] = useState<NoticePeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [saving, setSaving] = useState(false);

  // Main form — fields are pre-filled with editable suggestions (start = resignation
  // date, end = policy-derived), never saved until HR explicitly presses save.
  const [form, setForm] = useState({
    notice_period_start_date: '',
    notice_period_days: '',
    expected_last_working_day: '',
    early_relief_date: '',
    actual_last_working_day: '',
    notice_comments: '',
  });

  // Modals
  const [modal, setModal] = useState<'extension' | 'early-review' | 'complete' | null>(null);
  const [extForm, setExtForm] = useState({ notice_extension_date: '', extension_reason: '' });
  const [earlyReview, setEarlyReview] = useState({ early_release_date: '', notes: '' });
  const [completeDate, setCompleteDate] = useState('');

  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';

  useEffect(() => {
    if (!id) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const res = await offboardingService.getResignation(Number(id));
      setResignation(res);
      try {
        const np = await noticePeriodService.get(Number(id));
        setNotice(np);
        syncForm(np, res);
      } catch {
        setNotice(null);
        syncForm(null, res);
      }
    } catch {
      setError('Failed to load resignation details.');
    } finally {
      setLoading(false);
    }
  }

  function syncForm(np: NoticePeriod | null, res: ResignationRequest | null) {
    const months = res?.notice_policy_months ?? null;
    const resDate = res?.resignation_date || '';
    setForm({
      notice_period_start_date: np?.notice_period_start_date || resDate,
      notice_period_days: np?.notice_period_days != null
        ? String(np.notice_period_days)
        : months ? String(months * 30) : '',
      expected_last_working_day: np?.expected_last_working_day
        || res?.last_working_date
        || (resDate && months ? addMonthsStr(resDate, months) : ''),
      early_relief_date: np?.early_release_date || '',
      actual_last_working_day: np?.actual_last_working_day || '',
      notice_comments: np?.notice_comments || '',
    });
  }

  function buildPayload() {
    return {
      notice_period_start_date: form.notice_period_start_date || null,
      notice_period_days: form.notice_period_days ? Number(form.notice_period_days) : null,
      expected_last_working_day: form.expected_last_working_day || null,
      actual_last_working_day: form.actual_last_working_day || null,
      early_relief_date: form.early_relief_date || null,
      notice_comments: form.notice_comments,
    };
  }

  async function handleCreate() {
    if (!id) return;
    setSaving(true); setActionError(''); setSuccessMsg('');
    try {
      const np = await noticePeriodService.create(Number(id), buildPayload());
      setNotice(np);
      setSuccessMsg('Notice period started.');
      const res = await offboardingService.getResignation(Number(id));
      setResignation(res);
      syncForm(np, res);
    } catch (err) {
      setActionError(errMsg(err, 'Failed to start notice period.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate() {
    if (!id) return;
    setSaving(true); setActionError(''); setSuccessMsg('');
    try {
      const np = await noticePeriodService.update(Number(id), buildPayload());
      setNotice(np);
      syncForm(np, resignation);
      setSuccessMsg('Notice period updated.');
    } catch (err) {
      setActionError(errMsg(err, 'Failed to update notice period.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleExtension() {
    if (!id) return;
    setSaving(true); setActionError(''); setSuccessMsg('');
    try {
      const np = await noticePeriodService.recordExtension(
        Number(id), extForm.notice_extension_date, extForm.extension_reason,
      );
      setNotice(np);
      syncForm(np, resignation);
      setModal(null);
      setExtForm({ notice_extension_date: '', extension_reason: '' });
      setSuccessMsg('Notice extension recorded.');
    } catch (err) {
      setActionError(errMsg(err, 'Failed to record extension.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleEarlyReview(action: 'approve' | 'reject') {
    if (!id) return;
    setSaving(true); setActionError(''); setSuccessMsg('');
    try {
      const np = await noticePeriodService.reviewEarlyRelease(
        Number(id), action,
        action === 'approve' ? earlyReview.early_release_date : null,
        earlyReview.notes,
      );
      setNotice(np);
      syncForm(np, resignation);
      setModal(null);
      setEarlyReview({ early_release_date: '', notes: '' });
      setSuccessMsg(action === 'approve' ? 'Early release approved.' : 'Early release rejected.');
    } catch (err) {
      setActionError(errMsg(err, 'Failed to process early release.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    if (!id) return;
    setSaving(true); setActionError(''); setSuccessMsg('');
    try {
      const res = await noticePeriodService.complete(Number(id), completeDate);
      setResignation(res);
      const np = await noticePeriodService.get(Number(id));
      setNotice(np);
      syncForm(np, res);
      setModal(null);
      setSuccessMsg('Notice period completed. Employee marked as exited.');
    } catch (err) {
      setActionError(errMsg(err, 'Failed to complete notice period.'));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  if (!isHR) {
    return (
      <div>
        <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${id}`)} style={{ marginBottom: 8 }}>
          ← Back
        </button>
        <div className="alert alert-warning">Only HR can manage the notice period. You can view details on the request page.</div>
      </div>
    );
  }

  const completed = notice?.status === 'COMPLETED';
  const canCreate = !notice && resignation.status === 'APPROVED';
  const inNoticePeriod = resignation.status === 'NOTICE_PERIOD';
  const pendingEarlyRelease = notice?.status === 'EARLY_RELEASE_REQUESTED';

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${id}`)} style={{ marginBottom: 8 }}>
            ← Back
          </button>
          <h1 className="page-title">Notice Period</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {notice && (
          <span className="badge badge-it" style={{ fontSize: 14, padding: '6px 14px' }}>
            {notice.status_display}
          </span>
        )}
      </div>

      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}
      {successMsg && <div className="alert" style={{ marginBottom: 16, background: 'var(--success-bg, #ecfdf5)', color: 'var(--success, #047857)' }}>{successMsg}</div>}

      {!notice && !canCreate && (
        <div className="alert alert-warning">
          A notice period can only be started once the resignation is fully approved (current status: {resignation.status_display}).
        </div>
      )}

      {/* Pending early release banner */}
      {pendingEarlyRelease && (
        <div className="card" style={{ marginBottom: 16, borderLeft: '4px solid var(--warning, #d97706)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Early Release Requested</h3>
          <div className="detail-row"><span className="detail-label">Requested By</span><span className="detail-value">{notice.early_release_requested_by_name || '—'}</span></div>
          <div className="detail-row"><span className="detail-label">Requested At</span><span className="detail-value">{formatDateTime(notice.early_release_requested_at)}</span></div>
          <div className="detail-row" style={{ flexDirection: 'column', gap: 4 }}>
            <span className="detail-label">Reason</span>
            <span className="detail-value" style={{ marginLeft: 0, whiteSpace: 'pre-wrap' }}>{notice.early_release_request_reason}</span>
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={() => setModal('early-review')}>Review Early Release</button>
          </div>
        </div>
      )}

      {/* Main form */}
      {(canCreate || notice) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>Notice Period Details</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Notice Period Start Date</label>
              <input type="date" className="form-input" value={form.notice_period_start_date}
                disabled={completed}
                onChange={e => setForm(f => ({ ...f, notice_period_start_date: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Notice Period Days</label>
              <input type="number" min="0" className="form-input" value={form.notice_period_days}
                placeholder="e.g. 60"
                disabled={completed}
                onChange={e => setForm(f => ({ ...f, notice_period_days: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Expected Last Working Day</label>
              <input type="date" className="form-input" value={form.expected_last_working_day}
                min={form.notice_period_start_date || undefined}
                disabled={completed}
                onChange={e => setForm(f => ({ ...f, expected_last_working_day: e.target.value }))} />
              <small style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                Policy for this employee: {resignation.notice_policy_months} month{resignation.notice_policy_months === 1 ? '' : 's'}.
              </small>
            </div>
            <div className="form-group">
              <label className="form-label">Early Relieving Date (optional)</label>
              <input type="date" className="form-input" value={form.early_relief_date}
                min={form.notice_period_start_date || undefined}
                max={form.expected_last_working_day || undefined}
                disabled={completed}
                onChange={e => setForm(f => ({ ...f, early_relief_date: e.target.value }))} />
              <small style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                Fill in only if the employee is being released before the expected last working day.
              </small>
            </div>
            {notice && (
              <div className="form-group">
                <label className="form-label">Actual Last Working Day</label>
                <input type="date" className="form-input" value={form.actual_last_working_day}
                  disabled={completed}
                  onChange={e => setForm(f => ({ ...f, actual_last_working_day: e.target.value }))} />
              </div>
            )}
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">Comments</label>
              <textarea className="form-input" rows={3} value={form.notice_comments}
                disabled={completed}
                onChange={e => setForm(f => ({ ...f, notice_comments: e.target.value }))} />
            </div>
          </div>

          {!completed && (
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
              {canCreate ? (
                <button className="btn btn-primary" onClick={handleCreate} disabled={saving}>
                  {saving ? <><span className="btn-spinner" /> Starting…</> : 'Start Notice Period'}
                </button>
              ) : (
                <button className="btn btn-primary" onClick={handleUpdate} disabled={saving}>
                  {saving ? <><span className="btn-spinner" /> Saving…</> : 'Save Changes'}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Notice period actions */}
      {notice && inNoticePeriod && !completed && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Actions</h3>
          {pendingEarlyRelease ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
              Review the pending early release request above before recording an extension or completing the notice period.
            </p>
          ) : (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button className="btn btn-secondary" onClick={() => setModal('extension')}>Record Extension</button>
              <button className="btn btn-primary" onClick={() => { setCompleteDate(form.actual_last_working_day || form.early_relief_date || ''); setModal('complete'); }}>
                Complete Notice Period
              </button>
            </div>
          )}
        </div>
      )}

      {/* Read-only summary of prior actions */}
      {notice && (notice.notice_extension_date || notice.early_release_reviewed_by_name || notice.completed_by_name) && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>History</h3>
          {notice.notice_extension_date && (
            <>
              <div className="detail-row"><span className="detail-label">Extension Date</span><span className="detail-value">{formatDate(notice.notice_extension_date)}</span></div>
              <div className="detail-row"><span className="detail-label">Extension Reason</span><span className="detail-value">{notice.extension_reason}</span></div>
              <div className="detail-row"><span className="detail-label">Extension Recorded By</span><span className="detail-value">{notice.extension_recorded_by_name} · {formatDateTime(notice.extension_recorded_at)}</span></div>
            </>
          )}
          {notice.early_release_reviewed_by_name && (
            <>
              <div className="detail-row"><span className="detail-label">Early Release</span><span className="detail-value">{notice.early_release_approved ? `Approved (${formatDate(notice.early_release_date)})` : 'Rejected'}</span></div>
              <div className="detail-row"><span className="detail-label">Reviewed By</span><span className="detail-value">{notice.early_release_reviewed_by_name} · {formatDateTime(notice.early_release_reviewed_at)}</span></div>
              {notice.early_release_review_notes && (
                <div className="detail-row"><span className="detail-label">Review Notes</span><span className="detail-value">{notice.early_release_review_notes}</span></div>
              )}
            </>
          )}
          {notice.completed_by_name && (
            <>
              <div className="detail-row"><span className="detail-label">Completed By</span><span className="detail-value">{notice.completed_by_name} · {formatDateTime(notice.completed_at)}</span></div>
              <div className="detail-row"><span className="detail-label">Actual Last Working Day</span><span className="detail-value">{formatDate(notice.actual_last_working_day)}</span></div>
            </>
          )}
        </div>
      )}

      {/* Extension modal */}
      {modal === 'extension' && (
        <div className="modal-overlay" onClick={() => !saving && setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Record Notice Extension</h3></div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">New Extended Date <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={extForm.notice_extension_date}
                  onChange={e => setExtForm(f => ({ ...f, notice_extension_date: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Reason <span style={{ color: 'var(--danger)' }}>*</span></label>
                <textarea className="form-input" rows={3} value={extForm.extension_reason}
                  onChange={e => setExtForm(f => ({ ...f, extension_reason: e.target.value }))} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModal(null)} disabled={saving}>Back</button>
              <button className="btn btn-primary" onClick={handleExtension}
                disabled={saving || !extForm.notice_extension_date || !extForm.extension_reason.trim()}>
                {saving ? <><span className="btn-spinner" /> Saving…</> : 'Record Extension'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Early release review modal */}
      {modal === 'early-review' && (
        <div className="modal-overlay" onClick={() => !saving && setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Review Early Release Request</h3></div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Early Release Date (required to approve)</label>
                <input type="date" className="form-input" value={earlyReview.early_release_date}
                  onChange={e => setEarlyReview(f => ({ ...f, early_release_date: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea className="form-input" rows={3} value={earlyReview.notes}
                  onChange={e => setEarlyReview(f => ({ ...f, notes: e.target.value }))} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModal(null)} disabled={saving}>Back</button>
              <button className="btn btn-danger" onClick={() => handleEarlyReview('reject')} disabled={saving}>
                Reject
              </button>
              <button className="btn btn-primary" onClick={() => handleEarlyReview('approve')}
                disabled={saving || !earlyReview.early_release_date}>
                Approve
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Complete modal */}
      {modal === 'complete' && (
        <div className="modal-overlay" onClick={() => !saving && setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Complete Notice Period</h3></div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
                This finalizes the offboarding. The employee will be marked as <strong>Exited</strong>.
                This cannot be undone.
              </p>
              <div className="form-group">
                <label className="form-label">Actual Last Working Day <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={completeDate}
                  onChange={e => setCompleteDate(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setModal(null)} disabled={saving}>Back</button>
              <button className="btn btn-primary" onClick={handleComplete} disabled={saving || !completeDate}>
                {saving ? <><span className="btn-spinner" /> Completing…</> : 'Confirm Completion'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
