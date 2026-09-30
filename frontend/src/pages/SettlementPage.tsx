import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { settlementService, type SettlementMoneyPayload } from '../services/settlementService';
import type { FinalSettlement, FinalSettlementEmployeeView, ResignationRequest, SettlementStatus } from '../types';
import { formatDate, ktErrorMessage } from '../utils/kt';
import Icon from '../components/Icon';

const STATUS_BADGE: Record<SettlementStatus, string> = {
  DRAFT: 'badge-set-draft',
  PREPARED: 'badge-set-prepared',
  UNDER_REVIEW: 'badge-set-under-review',
  APPROVED: 'badge-set-approved',
  REJECTED: 'badge-set-rejected',
};

const ADDITIONS: { key: keyof SettlementMoneyPayload; label: string }[] = [
  { key: 'pending_salary', label: 'Pending Salary' },
  { key: 'leave_encashment', label: 'Leave Encashment' },
  { key: 'bonus', label: 'Bonus' },
  { key: 'incentives', label: 'Incentives' },
  { key: 'other_additions', label: 'Other Additions' },
];
const DEDUCTIONS: { key: keyof SettlementMoneyPayload; label: string }[] = [
  { key: 'notice_recovery', label: 'Notice Recovery' },
  { key: 'loan_deduction', label: 'Loan Deduction' },
  { key: 'advance_deduction', label: 'Advance Deduction' },
  { key: 'other_deductions', label: 'Other Deductions' },
];

function money(v: string | undefined) {
  if (v == null) return '—';
  const n = Number(v);
  return isNaN(n) ? v : `₹ ${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function isFull(s: FinalSettlement | FinalSettlementEmployeeView | null): s is FinalSettlement {
  return !!s && 'pending_salary' in s;
}

export default function SettlementPage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [settlement, setSettlement] = useState<FinalSettlement | FinalSettlementEmployeeView | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState<Record<string, string>>({});
  const [comments, setComments] = useState('');
  const [editing, setEditing] = useState(false);

  const [showApprove, setShowApprove] = useState(false);
  const [approveDate, setApproveDate] = useState('');
  const [approveComments, setApproveComments] = useState('');

  const isFinance = user?.role === 'FINANCE' || user?.role === 'ADMIN';
  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';

  const load = useCallback(async () => {
    try {
      const s = await settlementService.get(oid);
      setSettlement(s);
      setNotFound(false);
      if (isFull(s)) {
        const f: Record<string, string> = {};
        [...ADDITIONS, ...DEDUCTIONS].forEach(({ key }) => { f[key as string] = String(s[key as keyof FinalSettlement] ?? '0'); });
        setForm(f);
        setComments(s.comments || '');
      }
    } catch (err) {
      const e = err as { response?: { status?: number } };
      if (e?.response?.status === 404) setNotFound(true);
      else setError('Failed to load settlement.');
    }
  }, [oid]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await offboardingService.getResignation(oid);
        setResignation(res);
        await load();
      } catch {
        setError('Failed to load.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, [oid]);

  async function handleCreate() {
    setBusy(true); setActionError('');
    try {
      const payload: SettlementMoneyPayload = {};
      [...ADDITIONS, ...DEDUCTIONS].forEach(({ key }) => { payload[key] = '0'; });
      await settlementService.create(oid, payload);
      setMsg('Settlement created as draft.');
      await load();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to create settlement.'));
    } finally { setBusy(false); }
  }

  async function handleSave() {
    setBusy(true); setActionError('');
    try {
      const payload: SettlementMoneyPayload = { comments };
      [...ADDITIONS, ...DEDUCTIONS].forEach(({ key }) => { payload[key] = form[key as string] || '0'; });
      await settlementService.update(oid, payload);
      setEditing(false);
      setMsg('Settlement saved.');
      await load();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to save.'));
    } finally { setBusy(false); }
  }

  async function handleSubmit() {
    if (!confirm('Submit this settlement for HR review?')) return;
    setBusy(true); setActionError('');
    try { await settlementService.submit(oid); setMsg('Submitted for review.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to submit.')); }
    finally { setBusy(false); }
  }

  async function handleApprove() {
    setBusy(true); setActionError('');
    try {
      await settlementService.approve(oid, approveDate, approveComments);
      setShowApprove(false); setMsg('Settlement approved.'); await load();
    } catch (err) { setActionError(ktErrorMessage(err, 'Failed to approve.')); }
    finally { setBusy(false); }
  }

  async function handleReject() {
    const c = prompt('Reason for rejection (returns to Finance for correction):') || '';
    if (!c.trim()) return;
    setBusy(true); setActionError('');
    try { await settlementService.reject(oid, c); setMsg('Settlement returned to draft.'); await load(); }
    catch (err) { setActionError(ktErrorMessage(err, 'Failed to reject.')); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  const full = isFull(settlement) ? settlement : null;
  const canEdit = isFinance && full?.settlement_status === 'DRAFT';
  const canSubmit = isFinance && full?.settlement_status === 'DRAFT';
  const canReview = isHR && full?.settlement_status === 'UNDER_REVIEW';

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${oid}`)} style={{ marginBottom: 8 }}>← Back</button>
          <h1 className="page-title">Final Settlement</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {settlement && (
          <span className={`badge ${STATUS_BADGE[settlement.settlement_status]}`} style={{ fontSize: 14, padding: '6px 14px' }}>
            {settlement.status_display}
          </span>
        )}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      {/* No settlement yet */}
      {notFound && (
        <div className="card">
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="wallet" size={40} /></div>
            <h3>No settlement yet</h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              {isFinance ? 'Create a draft settlement to begin entering financial values.' : 'The final settlement has not been prepared yet.'}
            </p>
            {isFinance && <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={handleCreate} disabled={busy}>Create Settlement</button>}
          </div>
        </div>
      )}

      {/* Summary cards (everyone with view) */}
      {settlement && (
        <div className="settle-summary">
          <div className="settle-card gross"><div className="lbl">Gross Amount</div><div className="amt">{money(settlement.gross_amount)}</div></div>
          <div className="settle-card deduct"><div className="lbl">Total Deductions</div><div className="amt">{money(settlement.total_deductions)}</div></div>
          <div className="settle-card net"><div className="lbl">Net Settlement</div><div className="amt">{money(settlement.net_settlement)}</div></div>
        </div>
      )}

      {settlement && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="detail-row"><span className="detail-label">Status</span><span className="detail-value">{settlement.status_display}</span></div>
          <div className="detail-row"><span className="detail-label">Settlement Date</span><span className="detail-value">{settlement.settlement_date ? formatDate(settlement.settlement_date) : 'Not entered'}</span></div>
        </div>
      )}

      {/* Finance/HR breakdown */}
      {full && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>Breakdown</h3>
            {canEdit && !editing && <button className="btn btn-secondary" onClick={() => setEditing(true)}>Edit Values</button>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
            <div>
              <h4 style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>Additions</h4>
              {ADDITIONS.map(({ key, label }) => (
                <div className="detail-row" key={key as string}>
                  <span className="detail-label">{label}</span>
                  {editing ? (
                    <input type="number" step="0.01" min="0" className="form-input" style={{ maxWidth: 140 }}
                      value={form[key as string] ?? ''} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
                  ) : <span className="detail-value">{money(full[key as keyof FinalSettlement] as string)}</span>}
                </div>
              ))}
            </div>
            <div>
              <h4 style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>Deductions</h4>
              {DEDUCTIONS.map(({ key, label }) => (
                <div className="detail-row" key={key as string}>
                  <span className="detail-label">{label}</span>
                  {editing ? (
                    <input type="number" step="0.01" min="0" className="form-input" style={{ maxWidth: 140 }}
                      value={form[key as string] ?? ''} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
                  ) : <span className="detail-value">{money(full[key as keyof FinalSettlement] as string)}</span>}
                </div>
              ))}
            </div>
          </div>
          {editing && (
            <div className="form-group" style={{ marginTop: 12 }}>
              <label className="form-label">Comments</label>
              <textarea className="form-input" rows={2} value={comments} onChange={e => setComments(e.target.value)} />
            </div>
          )}
          {full.comments && !editing && (
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 12 }}><strong>Comments:</strong> {full.comments}</p>
          )}
          {editing && (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
              <button className="btn btn-secondary" onClick={() => { setEditing(false); load(); }} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={busy}>Save (totals recomputed by server)</button>
            </div>
          )}
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>Totals are calculated and validated by the backend.</p>
        </div>
      )}

      {/* Actions */}
      {full && (
        <div className="card">
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            {canSubmit && <button className="btn btn-primary" onClick={handleSubmit} disabled={busy || editing}>Submit for Review</button>}
            {canReview && <button className="btn btn-danger" onClick={handleReject} disabled={busy}>Reject</button>}
            {canReview && <button className="btn btn-primary" onClick={() => setShowApprove(true)} disabled={busy}>Approve</button>}
            {full.settlement_status === 'APPROVED' && <span style={{ color: 'var(--success)', fontWeight: 600 }}>✓ Approved</span>}
          </div>
        </div>
      )}

      {/* Approve modal */}
      {showApprove && (
        <div className="modal-overlay" onClick={() => !busy && setShowApprove(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <div className="modal-header"><h3>Approve Settlement</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <div className="form-group">
                <label className="form-label">Settlement Date <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={approveDate} onChange={e => setApproveDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Comments</label>
                <textarea className="form-input" rows={2} value={approveComments} onChange={e => setApproveComments(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowApprove(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleApprove} disabled={busy || !approveDate}>Confirm Approval</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
