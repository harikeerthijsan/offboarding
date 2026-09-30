import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { offboardingService } from '../services/offboardingService';
import type { ResignationReason } from '../types';

const REASONS: { value: ResignationReason; label: string }[] = [
  { value: 'BETTER_OPPORTUNITY', label: 'Better Opportunity' },
  { value: 'PERSONAL_REASONS', label: 'Personal Reasons' },
  { value: 'HIGHER_EDUCATION', label: 'Higher Education' },
  { value: 'RELOCATION', label: 'Relocation' },
  { value: 'HEALTH_REASONS', label: 'Health Reasons' },
  { value: 'FAMILY_COMMITMENT', label: 'Family Commitment' },
  { value: 'CAREER_CHANGE', label: 'Career Change' },
  { value: 'COMPENSATION', label: 'Compensation' },
  { value: 'WORK_ENVIRONMENT', label: 'Work Environment' },
  { value: 'OTHER', label: 'Other' },
];

const TODAY_LABEL = new Date().toLocaleDateString('en-US', {
  year: 'numeric', month: 'long', day: 'numeric',
});

export default function ResignationCreatePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    reason: '' as ResignationReason | '',
    notes: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState('');

  function validate() {
    const e: Record<string, string> = {};
    if (!form.reason) e.reason = 'Reason is required.';
    return e;
  }

  function handleChange(field: string, value: string) {
    setForm(f => ({ ...f, [field]: value }));
    if (errors[field]) setErrors(e => { const n = { ...e }; delete n[field]; return n; });
  }

  function handlePreview(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setShowModal(true);
  }

  async function handleConfirmSubmit() {
    setSubmitting(true);
    setApiError('');
    try {
      const resignation = await offboardingService.createResignation({
        reason: form.reason as ResignationReason,
        notes: form.notes,
      });
      // Auto-submit (DRAFT → SUBMITTED)
      try {
        await offboardingService.submitResignation(resignation.id);
      } catch {
        setShowModal(false);
        navigate(`/offboarding/${resignation.id}`);
        return;
      }
      setShowModal(false);
      navigate(`/offboarding/${resignation.id}`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setApiError(e?.response?.data?.detail || 'Failed to create resignation. Please try again.');
      setShowModal(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate('/offboarding')} style={{ marginBottom: 8 }}>
            ← Back
          </button>
          <h1 className="page-title">Submit Resignation</h1>
          <p className="page-subtitle">Fill in the details below and review before submitting.</p>
        </div>
      </div>

      {apiError && <div className="error-message" style={{ marginBottom: 16 }}>{apiError}</div>}

      <div className="card" style={{ maxWidth: 600 }}>
        <form onSubmit={handlePreview} noValidate>
          <div className="form-group">
            <label className="form-label">
              Reason for Resignation <span style={{ color: 'var(--danger)' }}>*</span>
            </label>
            <select
              className={`form-input${errors.reason ? ' error' : ''}`}
              value={form.reason}
              onChange={e => handleChange('reason', e.target.value)}
            >
              <option value="">Select a reason…</option>
              {REASONS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
            {errors.reason && <p className="form-error">{errors.reason}</p>}
          </div>

          <div className="form-group">
            <label className="form-label">Resignation Date</label>
            <input type="text" className="form-input" value={TODAY_LABEL} disabled readOnly />
            <p className="form-hint" style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              Set automatically to today's date.
            </p>
          </div>

          <div className="alert alert-warning" style={{ marginBottom: 16 }}>
            Your <strong>last working day</strong> will be calculated automatically from your notice
            period — <strong>1 month</strong> if your tenure is under 6 months, otherwise
            <strong> 2 months</strong> from the resignation date.
          </div>

          <div className="form-group">
            <label className="form-label">Additional Notes</label>
            <textarea
              className="form-input"
              rows={4}
              placeholder="Any additional context you would like to share…"
              value={form.notes}
              onChange={e => handleChange('notes', e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/offboarding')}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Review & Submit
            </button>
          </div>
        </form>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => !submitting && setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3>Confirm Resignation Submission</h3>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: 16, color: 'var(--text-secondary)' }}>
                Please review the details below before submitting. Your resignation will be sent to
                your manager for review.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                <div className="detail-row">
                  <span className="detail-label">Reason</span>
                  <span className="detail-value">
                    {REASONS.find(r => r.value === form.reason)?.label}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Resignation Date</span>
                  <span className="detail-value">{TODAY_LABEL}</span>
                </div>
                {form.notes && (
                  <div className="detail-row">
                    <span className="detail-label">Notes</span>
                    <span className="detail-value">{form.notes}</span>
                  </div>
                )}
              </div>
              <div className="alert alert-warning" style={{ marginTop: 16 }}>
                Once submitted, your resignation will be routed to your manager for review. Your
                employment status will change to <strong>Offboarding</strong>, and your last working
                day will be set based on your notice period.
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowModal(false)}
                disabled={submitting}
              >
                Go Back
              </button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmSubmit}
                disabled={submitting}
              >
                {submitting ? (
                  <><span className="btn-spinner" /> Submitting…</>
                ) : (
                  'Confirm & Submit'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
