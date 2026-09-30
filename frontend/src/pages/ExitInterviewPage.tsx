import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { settlementService, type ExitInterviewAnswersPayload } from '../services/settlementService';
import type { ExitInterview, ExitInterviewStatus, ResignationRequest } from '../types';
import { formatDate, formatDateTime, ktErrorMessage } from '../utils/kt';
import Icon from '../components/Icon';

const STATUS_BADGE: Record<ExitInterviewStatus, string> = {
  NOT_STARTED: 'badge-ei-not-started',
  IN_PROGRESS: 'badge-ei-in-progress',
  COMPLETED: 'badge-ei-completed',
  REVIEWED: 'badge-ei-reviewed',
};

const REASONS: { value: string; label: string }[] = [
  { value: '', label: '—' },
  { value: 'CAREER_GROWTH', label: 'Career Growth' },
  { value: 'NEW_OPPORTUNITY', label: 'New Opportunity' },
  { value: 'HIGHER_STUDIES', label: 'Higher Studies' },
  { value: 'PERSONAL_REASONS', label: 'Personal Reasons' },
  { value: 'RELOCATION', label: 'Relocation' },
  { value: 'COMPENSATION', label: 'Compensation' },
  { value: 'WORK_ENVIRONMENT', label: 'Work Environment' },
  { value: 'MANAGEMENT', label: 'Management' },
  { value: 'ROLE_CHANGE', label: 'Role Change' },
  { value: 'OTHER', label: 'Other' },
];

const RATINGS: { key: keyof ExitInterviewAnswersPayload; label: string }[] = [
  { key: 'overall_experience', label: 'Overall Experience' },
  { key: 'manager_feedback', label: 'Manager' },
  { key: 'work_environment_feedback', label: 'Work Environment' },
  { key: 'role_feedback', label: 'Role' },
  { key: 'growth_feedback', label: 'Career Growth' },
  { key: 'compensation_feedback', label: 'Compensation' },
];

function Rating({ value, onChange, disabled }: { value: number; onChange: (v: number) => void; disabled: boolean }) {
  return (
    <div className="rating-row">
      {[1, 2, 3, 4, 5].map(n => (
        <span key={n} className={`rating-opt${value === n ? ' selected' : ''}`}
          onClick={() => !disabled && onChange(n)} style={{ cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.7 : 1 }}>
          {n}
        </span>
      ))}
    </div>
  );
}

export default function ExitInterviewPage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [ei, setEi] = useState<ExitInterview | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<ExitInterviewAnswersPayload>({});
  const [hrNotes, setHrNotes] = useState('');

  // The only EMPLOYEE-role user the backend returns this interview to is its owner.
  const isOwner = user?.role === 'EMPLOYEE';
  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';

  const syncForm = (e: ExitInterview) => setForm({
    interview_date: e.interview_date ?? '',
    primary_reason: e.primary_reason || '', secondary_reason: e.secondary_reason || '',
    overall_experience: e.overall_experience, manager_feedback: e.manager_feedback,
    work_environment_feedback: e.work_environment_feedback, role_feedback: e.role_feedback,
    growth_feedback: e.growth_feedback, compensation_feedback: e.compensation_feedback,
    what_went_well: e.what_went_well, what_could_improve: e.what_could_improve,
    suggestions: e.suggestions, additional_comments: e.additional_comments,
    would_recommend: e.would_recommend, would_rejoin: e.would_rejoin,
  });

  const load = useCallback(async () => {
    try {
      const data = await settlementService.getInterview(oid);
      setEi(data); setNotFound(false); syncForm(data); setHrNotes(data.hr_review_notes || '');
    } catch (err) {
      const e = err as { response?: { status?: number } };
      if (e?.response?.status === 404) setNotFound(true);
      else setError('Failed to load exit interview.');
    }
  }, [oid]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await offboardingService.getResignation(oid);
        setResignation(res);
        await load();
      } catch { setError('Failed to load.'); }
      finally { setLoading(false); }
    })();
    // eslint-disable-next-line
  }, [oid]);

  // HR conducts the exit interview after the notice period, so HR (and Admin) can
  // edit the answers — including the reason to leave — while it is in progress.
  const editable = ei?.status === 'IN_PROGRESS' && (isOwner || isHR);

  async function handleStart() {
    setBusy(true); setActionError('');
    try { await settlementService.startInterview(oid); setMsg('Interview started.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to start.')); }
    finally { setBusy(false); }
  }

  async function handleSave() {
    setBusy(true); setActionError('');
    try {
      const payload: ExitInterviewAnswersPayload = { ...form, interview_date: form.interview_date || null };
      await settlementService.saveInterview(oid, payload);
      setMsg('Draft saved.'); await load();
    } catch (err) { setActionError(ktErrorMessage(err, 'Failed to save.')); }
    finally { setBusy(false); }
  }

  async function handleSubmit() {
    if (!confirm('Submit your exit interview? You will not be able to edit it afterwards unless HR reopens it.')) return;
    setBusy(true); setActionError('');
    try { await settlementService.saveInterview(oid, { ...form, interview_date: form.interview_date || null }); await settlementService.submitInterview(oid); setMsg('Interview submitted.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to submit.')); }
    finally { setBusy(false); }
  }

  async function handleReview() {
    setBusy(true); setActionError('');
    try { await settlementService.reviewInterview(oid, hrNotes); setMsg('Marked as reviewed.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to review.')); }
    finally { setBusy(false); }
  }

  async function handleReopen() {
    setBusy(true); setActionError('');
    try { await settlementService.reopenInterview(oid); setMsg('Interview reopened.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to reopen.')); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  const set = <K extends keyof ExitInterviewAnswersPayload>(k: K, v: ExitInterviewAnswersPayload[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${oid}`)} style={{ marginBottom: 8 }}>← Back</button>
          <h1 className="page-title">Exit Interview</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {ei && <span className={`badge ${STATUS_BADGE[ei.status]}`} style={{ fontSize: 14, padding: '6px 14px' }}>{ei.status_display}</span>}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      {notFound && (
        <div className="card"><div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
          <div className="empty-icon"><Icon name="note" size={40} /></div>
          <h3>Exit interview not started</h3>
          <p style={{ color: 'var(--text-secondary)' }}>{isOwner ? 'Start your exit interview to share your feedback.' : 'The employee has not started their exit interview.'}</p>
          {(isOwner || isHR) && <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={handleStart} disabled={busy}>Start Exit Interview</button>}
        </div></div>
      )}

      {ei && (
        <>
          {/* Basic info */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Basic Information</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Interview Date</label>
                {editable ? (
                  <input type="date" className="form-input" value={form.interview_date ?? ''} onChange={e => set('interview_date', e.target.value)} />
                ) : <div>{ei.interview_date ? formatDate(ei.interview_date) : 'Not entered'}</div>}
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Conducted By</label>
                <div>{ei.conducted_by_name || '—'}</div>
              </div>
            </div>
          </div>

          {/* Reasons */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Reason for Leaving</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Primary Reason</label>
                {editable ? (
                  <select className="form-input" value={form.primary_reason ?? ''} onChange={e => set('primary_reason', e.target.value)}>
                    {REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                ) : <div>{REASONS.find(r => r.value === ei.primary_reason)?.label || '—'}</div>}
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Secondary Reason</label>
                {editable ? (
                  <select className="form-input" value={form.secondary_reason ?? ''} onChange={e => set('secondary_reason', e.target.value)}>
                    {REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                ) : <div>{REASONS.find(r => r.value === ei.secondary_reason)?.label || '—'}</div>}
              </div>
            </div>
          </div>

          {/* Feedback ratings */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Employee Feedback (1 = Poor, 5 = Excellent)</h3>
            {RATINGS.map(({ key, label }) => (
              <div className="detail-row" key={key as string}>
                <span className="detail-label">{label}</span>
                <span className="detail-value">
                  <Rating value={(form[key] as number) ?? 0} onChange={v => set(key, v)} disabled={!editable} />
                </span>
              </div>
            ))}
          </div>

          {/* Open feedback */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Open Feedback</h3>
            {([['what_went_well', 'What went well?'], ['what_could_improve', 'What could we improve?'],
               ['suggestions', 'Suggestions'], ['additional_comments', 'Additional comments']] as const).map(([k, label]) => (
              <div className="form-group" key={k}>
                <label className="form-label">{label}</label>
                {editable ? (
                  <textarea className="form-input" rows={2} value={(form[k] as string) ?? ''} onChange={e => set(k, e.target.value)} />
                ) : <div style={{ whiteSpace: 'pre-wrap' }}>{(ei[k] as string) || '—'}</div>}
              </div>
            ))}
          </div>

          {/* Future relationship */}
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Future Relationship</h3>
            <div className="detail-row">
              <span className="detail-label">Would you recommend the company?</span>
              <span className="detail-value">
                {editable ? (
                  <label style={{ display: 'inline-flex', gap: 12 }}>
                    <span><input type="radio" checked={form.would_recommend === true} onChange={() => set('would_recommend', true)} /> Yes</span>
                    <span><input type="radio" checked={form.would_recommend === false} onChange={() => set('would_recommend', false)} /> No</span>
                  </label>
                ) : (ei.would_recommend == null ? '—' : ei.would_recommend ? 'Yes' : 'No')}
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Would you consider rejoining?</span>
              <span className="detail-value">
                {editable ? (
                  <label style={{ display: 'inline-flex', gap: 12 }}>
                    <span><input type="radio" checked={form.would_rejoin === true} onChange={() => set('would_rejoin', true)} /> Yes</span>
                    <span><input type="radio" checked={form.would_rejoin === false} onChange={() => set('would_rejoin', false)} /> No</span>
                  </label>
                ) : (ei.would_rejoin == null ? '—' : ei.would_rejoin ? 'Yes' : 'No')}
              </span>
            </div>
          </div>

          {/* HR review (separate from answers) */}
          {(isHR || ei.hr_review_notes) && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>HR Review</h3>
              {isHR && ei.status === 'COMPLETED' ? (
                <div className="form-group">
                  <label className="form-label">HR Review Notes</label>
                  <textarea className="form-input" rows={3} value={hrNotes} onChange={e => setHrNotes(e.target.value)} />
                </div>
              ) : (
                <>
                  <div className="detail-row"><span className="detail-label">Notes</span><span className="detail-value">{ei.hr_review_notes || '—'}</span></div>
                  <div className="detail-row"><span className="detail-label">Reviewed By</span><span className="detail-value">{ei.reviewed_by_name || '—'}{ei.reviewed_at ? ` · ${formatDateTime(ei.reviewed_at)}` : ''}</span></div>
                </>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="card">
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              {editable && <button className="btn btn-secondary" onClick={handleSave} disabled={busy}>Save Draft</button>}
              {editable && <button className="btn btn-primary" onClick={handleSubmit} disabled={busy}>Submit for Review</button>}
              {isHR && ei.status === 'COMPLETED' && <button className="btn btn-secondary" onClick={handleReopen} disabled={busy}>Reopen</button>}
              {isHR && ei.status === 'COMPLETED' && <button className="btn btn-primary" onClick={handleReview} disabled={busy}>Mark Reviewed</button>}
              {isHR && ei.status === 'REVIEWED' && <button className="btn btn-secondary" onClick={handleReopen} disabled={busy}>Reopen</button>}
              {ei.status === 'REVIEWED' && <span style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Reviewed</span>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
