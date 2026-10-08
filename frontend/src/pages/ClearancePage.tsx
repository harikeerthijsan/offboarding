import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { clearanceService } from '../services/clearanceService';
import type {
  ResignationRequest, DepartmentClearance, AssetClearance, Asset,
  ClearanceSummary, ClearanceDepartment, AssetCondition,
} from '../types';
import { formatDate, ktErrorMessage } from '../utils/kt';
import {
  ASSET_CLR_STATUS_BADGE, ASSET_CONDITIONS, CLEARANCE_DEPARTMENTS,
} from '../utils/clearance';
import ClearanceDepartmentCard from '../components/ClearanceDepartmentCard';
import Icon from '../components/Icon';

type Tab = 'departments' | 'assets';

export default function ClearancePage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [tab, setTab] = useState<Tab>('departments');
  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [summary, setSummary] = useState<ClearanceSummary | null>(null);
  const [depts, setDepts] = useState<DepartmentClearance[]>([]);
  const [assetClearances, setAssetClearances] = useState<AssetClearance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [actionError, setActionError] = useState('');

  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';
  const canAddAssets = ['IT', 'ADMIN', 'HR'].includes(user?.role ?? '');

  // add-department modal
  const [showAddDept, setShowAddDept] = useState(false);
  const [newDept, setNewDept] = useState<ClearanceDepartment>('IT');

  // add-asset modal
  const [showAddAsset, setShowAddAsset] = useState(false);
  const [candidateAssets, setCandidateAssets] = useState<Asset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<number | ''>('');

  // return modal
  const [returnFor, setReturnFor] = useState<AssetClearance | null>(null);
  const [returnDate, setReturnDate] = useState('');
  const [returnCondition, setReturnCondition] = useState<AssetCondition>('GOOD');
  const [returnRemarks, setReturnRemarks] = useState('');
  const [busy, setBusy] = useState(false);

  // verify / reject / damaged modal
  const [verifyModal, setVerifyModal] = useState<{ ac: AssetClearance; action: 'verify' | 'reject' | 'mark_damaged' } | null>(null);
  const [verifyComments, setVerifyComments] = useState('');

  // employee asset declaration
  const [declConfirmed, setDeclConfirmed] = useState(false);
  const [declNotes, setDeclNotes] = useState('');

  const load = useCallback(async () => {
    const [sum, d, ac] = await Promise.all([
      clearanceService.summary(oid),
      clearanceService.listClearances(oid),
      clearanceService.listAssetClearances(oid),
    ]);
    setSummary(sum);
    setDepts(d);
    setAssetClearances(ac);
  }, [oid]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await offboardingService.getResignation(oid);
        setResignation(res);
        await load();
      } catch {
        setError('Failed to load clearance information.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, [oid]);

  async function refresh() {
    try { await load(); } catch { /* ignore */ }
  }

  async function handleAddDept() {
    setBusy(true); setActionError('');
    try {
      await clearanceService.createClearance(oid, newDept);
      setShowAddDept(false);
      setMsg(`${newDept} clearance added.`);
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to add clearance.'));
    } finally { setBusy(false); }
  }

  async function openAddAsset() {
    setActionError('');
    try {
      if (resignation?.employee_id) {
        // employee_id is the code; need numeric employee id — use asset assigned filter via employee assets endpoint
      }
      // Load assets assigned to this employee that are not yet in clearance
      const assigned = await clearanceService.listAssets({ status: 'ASSIGNED' });
      const existing = new Set(assetClearances.map(a => a.asset));
      // Filter to the offboarding employee's assets by matching employee code
      const mine = assigned.filter(a => a.assigned_to_employee_id === resignation?.employee_id && !existing.has(a.id));
      setCandidateAssets(mine);
    } catch {
      setCandidateAssets([]);
    }
    setSelectedAsset('');
    setShowAddAsset(true);
  }

  async function handleAddAsset() {
    if (!selectedAsset) return;
    setBusy(true); setActionError('');
    try {
      await clearanceService.addAssetClearance(oid, Number(selectedAsset));
      setShowAddAsset(false);
      setMsg('Asset added to clearance.');
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to add asset.'));
    } finally { setBusy(false); }
  }

  function openReturn(ac: AssetClearance) {
    setReturnFor(ac);
    setReturnDate('');
    setReturnCondition('GOOD');
    setReturnRemarks('');
  }

  async function handleRecordReturn() {
    if (!returnFor) return;
    setBusy(true); setActionError('');
    try {
      await clearanceService.recordReturn(returnFor.id, returnDate, returnCondition, returnRemarks);
      setReturnFor(null);
      setMsg('Asset return recorded.');
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to record return.'));
    } finally { setBusy(false); }
  }

  // 'mark_lost' is immediate (with confirm); verify/reject/mark_damaged open a modal.
  async function handleVerify(ac: AssetClearance, action: 'verify' | 'reject' | 'mark_damaged' | 'mark_lost') {
    if (action === 'mark_lost') {
      if (!confirm(`Mark "${ac.asset_name}" as LOST? This cannot be returned afterwards.`)) return;
      setActionError('');
      try { await clearanceService.verifyAsset(ac.id, 'mark_lost', ''); await refresh(); }
      catch (err) { setActionError(ktErrorMessage(err, 'Action failed.')); }
      return;
    }
    setVerifyComments('');
    setVerifyModal({ ac, action });
  }

  async function confirmVerify() {
    if (!verifyModal) return;
    const { ac, action } = verifyModal;
    // reason required for reject and damaged; optional note for a clean verify
    if ((action === 'reject' || action === 'mark_damaged') && !verifyComments.trim()) return;
    setBusy(true); setActionError('');
    try {
      await clearanceService.verifyAsset(ac.id, action, verifyComments);
      setVerifyModal(null);
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Action failed.'));
    } finally { setBusy(false); }
  }

  async function handleMarkComplete() {
    if (!confirm('Mark the entire clearance complete?\n\nAll required departments and assets must be cleared.')) return;
    setActionError(''); setMsg('');
    try {
      await clearanceService.markComplete(oid);
      setMsg('Clearance marked complete.');
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Could not mark clearance complete.'));
    }
  }

  async function handleSubmitDeclaration() {
    setBusy(true); setActionError('');
    try {
      await clearanceService.submitAssetDeclaration(oid, declNotes);
      setMsg('Your asset return declaration has been submitted.');
      setDeclConfirmed(false);
      setDeclNotes('');
      await refresh();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to submit declaration.'));
    } finally { setBusy(false); }
  }

  function canActAsset(ac: AssetClearance): boolean {
    return ['IT', 'ADMIN', 'HR'].includes(user?.role ?? '') && ac.status !== 'CLEARED' && ac.status !== 'LOST';
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation || !summary) return null;

  const d = summary.departments;
  const a = summary.assets;
  const isOwner = resignation.employee_user_id === user?.id;
  const declarationAvailable = ['APPROVED', 'NOTICE_PERIOD'].includes(resignation.status);

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${oid}`)} style={{ marginBottom: 8 }}>← Back</button>
          <h1 className="page-title">Clearance</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {isHR && (
          <button className="btn btn-secondary" onClick={handleMarkComplete}
            disabled={d.total === 0 || summary.clearance_completed}>
            {summary.clearance_completed ? 'Clearance Complete ✓' : 'Mark Clearance Complete'}
          </button>
        )}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      {/* Step 1 — Employee asset-return declaration. This comes BEFORE IT asset
          clearance: the employee declares assets returned, which then opens the
          IT asset clearance. */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Step 1 · Employee Asset Declaration</h3>

        {summary.asset_declaration_submitted ? (
          <div className="alert" style={{ background: '#ecfdf5', color: '#047857', padding: 14, borderRadius: 8 }}>
            <strong>✓ Declaration submitted.</strong>
            <div style={{ marginTop: 6, fontSize: 14 }}>
              {summary.asset_declaration_by_name ? `${summary.asset_declaration_by_name} ` : 'The employee '}
              declared that all company assets have been returned on {formatDate(summary.asset_declaration_at)}.
              IT asset clearance is now in progress below.
            </div>
            {summary.asset_declaration_notes && (
              <div style={{ marginTop: 8, fontSize: 14, whiteSpace: 'pre-wrap' }}>
                <span style={{ color: 'var(--text-muted)' }}>Note: </span>{summary.asset_declaration_notes}
              </div>
            )}
          </div>
        ) : isOwner && declarationAvailable ? (
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
              First, please confirm that you have returned or submitted all company assets assigned to you
              (laptop, ID card, access card, devices, etc.). Once you submit this declaration, IT will begin
              the asset clearance.
            </p>
            <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer', marginBottom: 12 }}>
              <input type="checkbox" checked={declConfirmed} onChange={e => setDeclConfirmed(e.target.checked)} style={{ marginTop: 3 }} />
              <span style={{ fontSize: 14 }}>
                I declare that I have returned/submitted all company assets assigned to me, and that I have
                no outstanding company property in my possession.
              </span>
            </label>
            <div className="form-group">
              <label className="form-label">Description <span style={{ color: 'var(--text-muted)' }}>(optional)</span></label>
              <textarea className="form-input" rows={3} value={declNotes} onChange={e => setDeclNotes(e.target.value)}
                placeholder="Any notes about the assets you returned, pending items, or remarks…" />
            </div>
            <div style={{ textAlign: 'right' }}>
              <button className="btn btn-primary" onClick={handleSubmitDeclaration} disabled={busy || !declConfirmed}>
                {busy ? <><span className="btn-spinner" /> Submitting…</> : 'Submit Declaration'}
              </button>
            </div>
          </div>
        ) : (
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
            {isOwner
              ? 'The asset declaration becomes available once your offboarding is approved and in progress.'
              : 'Waiting for the employee to submit their asset-return declaration. IT asset clearance will begin once they do.'}
          </p>
        )}
      </div>

      {/* Progress summary */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Department Clearance</h3>
          <div className="kt-stat-grid">
            <div className="kt-stat"><div className="num">{d.total}</div><div className="lbl">Total</div></div>
            <div className="kt-stat"><div className="num">{d.cleared}</div><div className="lbl">Cleared</div></div>
            <div className="kt-stat"><div className="num">{d.in_progress}</div><div className="lbl">In Progress</div></div>
            <div className="kt-stat"><div className="num">{d.pending}</div><div className="lbl">Pending</div></div>
            <div className="kt-stat"><div className="num">{d.rejected}</div><div className="lbl">Rejected</div></div>
          </div>
        </div>
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Asset Clearance</h3>
          <div className="kt-stat-grid">
            <div className="kt-stat"><div className="num">{a.total}</div><div className="lbl">Total</div></div>
            <div className="kt-stat"><div className="num">{a.returned}</div><div className="lbl">Returned</div></div>
            <div className="kt-stat"><div className="num">{a.cleared}</div><div className="lbl">Cleared</div></div>
            <div className="kt-stat"><div className="num">{a.pending}</div><div className="lbl">Pending</div></div>
            <div className="kt-stat"><div className="num">{a.damaged + a.lost}</div><div className="lbl">Damaged/Lost</div></div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tab-bar" style={{ marginBottom: 16 }}>
        <button className={`tab-btn${tab === 'departments' ? ' active' : ''}`} onClick={() => setTab('departments')}>Departments</button>
        <button className={`tab-btn${tab === 'assets' ? ' active' : ''}`} onClick={() => setTab('assets')}>Assets</button>
      </div>

      {/* Departments */}
      {tab === 'departments' && (
        <div>
          {isHR && (
            <div style={{ marginBottom: 12, textAlign: 'right' }}>
              <button className="btn btn-primary" onClick={() => setShowAddDept(true)}>+ Add Department</button>
            </div>
          )}
          {depts.length === 0 ? (
            <div className="card"><div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
              <div className="empty-icon"><Icon name="folder" size={40} /></div><h3>No department clearances</h3>
              <p style={{ color: 'var(--text-secondary)' }}>{isHR ? 'Add the departments that must clear this employee.' : 'No clearances set up yet.'}</p>
            </div></div>
          ) : (
            depts.map(dc => (
              <ClearanceDepartmentCard key={dc.id} clearance={dc} onChanged={refresh} />
            ))
          )}
        </div>
      )}

      {/* Assets */}
      {tab === 'assets' && (
        <div className="card">
          {canAddAssets && (
            <div style={{ marginBottom: 12, textAlign: 'right' }}>
              <button className="btn btn-primary" onClick={openAddAsset}>+ Add Asset to Clearance</button>
            </div>
          )}
          {assetClearances.length === 0 ? (
            <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
              <div className="empty-icon"><Icon name="laptop" size={40} /></div><h3>No assets in clearance</h3>
              <p style={{ color: 'var(--text-secondary)' }}>Add the employee's assigned assets to track their return.</p>
            </div>
          ) : (
            <table className="kt-table">
              <thead>
                <tr><th>Asset</th><th>Serial</th><th>Return Date</th><th>Condition</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                {assetClearances.map(ac => (
                  <tr key={ac.id}>
                    <td>{ac.asset_name} <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>({ac.asset_code})</span></td>
                    <td>{ac.serial_number || '—'}</td>
                    <td>{formatDate(ac.return_date)}</td>
                    <td>{ac.condition_display || '—'}</td>
                    <td><span className={`badge ${ASSET_CLR_STATUS_BADGE[ac.status]}`}>{ac.status_display}</span></td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {canActAsset(ac) && ac.status === 'RETURN_PENDING' && (
                        <>
                          <button className="btn btn-ghost" onClick={() => openReturn(ac)}>Record Return</button>
                          <button className="btn btn-ghost" onClick={() => handleVerify(ac, 'mark_lost')}>Lost</button>
                        </>
                      )}
                      {canActAsset(ac) && (ac.status === 'RETURNED' || ac.status === 'REJECTED') && (
                        <>
                          {ac.status === 'REJECTED' && <button className="btn btn-ghost" onClick={() => openReturn(ac)}>Re-record</button>}
                          <button className="btn btn-ghost" onClick={() => handleVerify(ac, 'verify')}>Verify</button>
                          <button className="btn btn-ghost" onClick={() => handleVerify(ac, 'reject')}>Reject</button>
                          <button className="btn btn-ghost" onClick={() => handleVerify(ac, 'mark_damaged')}>Damaged</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Add department modal */}
      {showAddDept && (
        <div className="modal-overlay" onClick={() => !busy && setShowAddDept(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <div className="modal-header"><h3>Add Department Clearance</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <div className="form-group">
                <label className="form-label">Department</label>
                <select className="form-input" value={newDept} onChange={e => setNewDept(e.target.value as ClearanceDepartment)}>
                  {CLEARANCE_DEPARTMENTS.map(dep => <option key={dep.value} value={dep.value}>{dep.label}</option>)}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowAddDept(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAddDept} disabled={busy}>Add</button>
            </div>
          </div>
        </div>
      )}

      {/* Add asset modal */}
      {showAddAsset && (
        <div className="modal-overlay" onClick={() => !busy && setShowAddAsset(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Add Asset to Clearance</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              {candidateAssets.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)' }}>No assignable assets found for this employee. Assign assets in the asset catalogue first.</p>
              ) : (
                <div className="form-group">
                  <label className="form-label">Asset</label>
                  <select className="form-input" value={selectedAsset} onChange={e => setSelectedAsset(Number(e.target.value))}>
                    <option value="">Select an asset…</option>
                    {candidateAssets.map(as => <option key={as.id} value={as.id}>{as.asset_name} ({as.asset_id})</option>)}
                  </select>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowAddAsset(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleAddAsset} disabled={busy || !selectedAsset}>Add</button>
            </div>
          </div>
        </div>
      )}

      {/* Record return modal */}
      {returnFor && (
        <div className="modal-overlay" onClick={() => !busy && setReturnFor(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Record Asset Return</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>{returnFor.asset_name} ({returnFor.asset_code})</p>
              <div className="form-group">
                <label className="form-label">Return Date <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input type="date" className="form-input" value={returnDate} onChange={e => setReturnDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Condition <span style={{ color: 'var(--danger)' }}>*</span></label>
                <select className="form-input" value={returnCondition} onChange={e => setReturnCondition(e.target.value as AssetCondition)}>
                  {ASSET_CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Remarks</label>
                <textarea className="form-input" rows={2} value={returnRemarks} onChange={e => setReturnRemarks(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setReturnFor(null)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleRecordReturn} disabled={busy || !returnDate}>Record Return</button>
            </div>
          </div>
        </div>
      )}

      {/* Verify / Reject / Damaged modal */}
      {verifyModal && (() => {
        const { ac, action } = verifyModal;
        const isReject = action === 'reject';
        const isDamaged = action === 'mark_damaged';
        const required = isReject || isDamaged;
        const title = isReject ? 'Reject Asset' : isDamaged ? 'Mark Asset Damaged' : 'Verify Asset';
        const label = isReject ? 'Reason for Rejection' : isDamaged ? 'Damage Details' : 'Note (if any damages)';
        const confirmLabel = isReject ? 'Confirm Rejection' : isDamaged ? 'Mark Damaged' : 'Verify & Clear';
        return (
          <div className="modal-overlay" onClick={() => !busy && setVerifyModal(null)}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
              <div className="modal-header"><h3>{title}</h3></div>
              <div className="modal-body">
                {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>
                  {ac.asset_name} ({ac.asset_code})
                </p>
                <div className="form-group">
                  <label className="form-label">
                    {label} {required ? <span style={{ color: 'var(--danger)' }}>*</span> : '(optional)'}
                  </label>
                  <textarea className="form-input" rows={3} value={verifyComments}
                    onChange={e => setVerifyComments(e.target.value)}
                    placeholder={isReject ? 'Why is this asset being rejected?…'
                      : isDamaged ? 'Describe the damage…'
                      : 'Note any damage or condition remarks (optional)…'} />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-secondary" onClick={() => setVerifyModal(null)} disabled={busy}>Cancel</button>
                <button className={`btn ${isReject ? 'btn-danger' : 'btn-primary'}`}
                  onClick={confirmVerify} disabled={busy || (required && !verifyComments.trim())}>
                  {busy ? <><span className="btn-spinner" /> Processing…</> : confirmLabel}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
