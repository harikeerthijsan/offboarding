import { useState } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import { clearanceService } from '../services/clearanceService';
import type { DepartmentClearance } from '../types';
import { formatDate, ktErrorMessage } from '../utils/kt';
import { DEPT_STATUS_BADGE } from '../utils/clearance';
import Modal from './Modal';

interface Props {
  clearance: DepartmentClearance;
  onChanged: () => void;
}

// Which role may act on each department (mirrors backend CLEARANCE_DEPARTMENT_ROLES).
// Mirrors backend CLEARANCE_DEPARTMENT_ROLES — HR can also clear Finance.
const DEPT_ROLES: Record<string, string[]> = {
  IT: ['IT', 'ADMIN'],
  ADMIN: ['ADMIN'],
  FINANCE: ['FINANCE', 'HR', 'ADMIN'],
  HR: ['HR', 'ADMIN'],
  MANAGER: ['MANAGER', 'ADMIN'],
};

export default function ClearanceDepartmentCard({ clearance, onChanged }: Props) {
  const { user } = useAuthContext();
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [newItem, setNewItem] = useState('');
  const [showClear, setShowClear] = useState(false);
  const [clearDate, setClearDate] = useState('');
  const [clearComments, setClearComments] = useState('');

  const role = user?.role ?? '';
  const isHR = role === 'HR' || role === 'ADMIN';
  const canAct = (DEPT_ROLES[clearance.department] || []).includes(role);
  const isFinal = clearance.status === 'CLEARED' || clearance.status === 'NOT_APPLICABLE';

  const items = clearance.checklist_items;
  const pendingCount = items.filter(i => i.status === 'PENDING').length;

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError('');
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(ktErrorMessage(err, 'Action failed.'));
    } finally {
      setBusy(false);
    }
  }

  async function addItem() {
    if (!newItem.trim()) return;
    await run(async () => {
      await clearanceService.addChecklistItem(clearance.id, newItem);
      setNewItem('');
    });
  }

  async function doClear() {
    await run(async () => {
      await clearanceService.clearanceAction(clearance.id, 'clear', { clearance_date: clearDate, comments: clearComments });
      setShowClear(false); setClearDate(''); setClearComments('');
    });
  }

  async function doReject() {
    const comments = prompt('Reason for rejecting this clearance:') || '';
    if (!comments.trim()) return;
    await run(() => clearanceService.clearanceAction(clearance.id, 'reject', { comments }));
  }

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="clr-dept-row" style={{ border: 'none', padding: 0, marginBottom: expanded ? 12 : 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="dept-name">{clearance.department_display}</span>
          <span className={`badge ${DEPT_STATUS_BADGE[clearance.status]}`}>{clearance.status_display}</span>
          {clearance.clearance_date && (
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Cleared {formatDate(clearance.clearance_date)}</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => setExpanded(e => !e)}>
            {expanded ? 'Hide' : `Checklist (${items.length})`}
          </button>
          {canAct && !isFinal && (
            <>
              <button className="btn btn-danger" onClick={doReject} disabled={busy}>Reject</button>
              <button className="btn btn-primary" onClick={() => setShowClear(true)} disabled={busy}>Clear</button>
            </>
          )}
          {canAct && clearance.status === 'REJECTED' && (
            <button className="btn btn-secondary" onClick={() => run(() => clearanceService.clearanceAction(clearance.id, 'reopen', {}))} disabled={busy}>Reopen</button>
          )}
        </div>
      </div>

      {error && <div className="error-message" style={{ marginTop: 8 }}>{error}</div>}
      {clearance.comments && (
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>
          <strong>Comments:</strong> {clearance.comments}
        </p>
      )}

      {expanded && (
        <div style={{ marginTop: 12 }}>
          {items.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No checklist items.</p>}
          {items.map(item => (
            <div key={item.id} className="checklist-item">
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span className={`checklist-check ${item.status === 'COMPLETED' ? 'done' : item.status === 'NOT_APPLICABLE' ? 'na' : ''}`}>
                  {item.status === 'COMPLETED' ? '✓' : item.status === 'NOT_APPLICABLE' ? '–' : ''}
                </span>
                <div>
                  <div style={{ fontWeight: 500 }}>{item.title}</div>
                  {item.description && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.description}</div>}
                  {item.comments && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.comments}</div>}
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {item.status_display}{item.completed_by_name ? ` · ${item.completed_by_name}` : ''}
                  </div>
                </div>
              </div>
              {canAct && !isFinal && (
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  {item.status !== 'COMPLETED' && (
                    <button className="btn btn-ghost" onClick={() => run(() => clearanceService.checklistAction(item.id, 'complete'))} disabled={busy}>Complete</button>
                  )}
                  {item.status === 'PENDING' && (
                    <button className="btn btn-ghost" onClick={() => run(() => clearanceService.checklistAction(item.id, 'not_applicable'))} disabled={busy}>N/A</button>
                  )}
                  {item.status !== 'PENDING' && (
                    <button className="btn btn-ghost" onClick={() => run(() => clearanceService.checklistAction(item.id, 'reset'))} disabled={busy}>Reset</button>
                  )}
                </div>
              )}
            </div>
          ))}

          {(isHR || canAct) && !isFinal && (
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <input className="form-input" placeholder="New checklist item…" value={newItem} onChange={e => setNewItem(e.target.value)} />
              <button className="btn btn-secondary" onClick={addItem} disabled={busy || !newItem.trim()}>Add</button>
            </div>
          )}
          {pendingCount > 0 && (
            <p style={{ fontSize: 12, color: 'var(--warning)', marginTop: 8 }}>
              {pendingCount} item(s) still pending — resolve all before clearing.
            </p>
          )}
        </div>
      )}

      {/* Clear modal */}
      {showClear && (
        <Modal onClose={() => !busy && setShowClear(false)} maxWidth={420}>
          <div className="modal-header"><h3>Clear {clearance.department_display}</h3></div>
          <div className="modal-body">
            {error && <div className="error-message" style={{ marginBottom: 12 }}>{error}</div>}
            <div className="form-group">
              <label className="form-label">Clearance Date <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input type="date" className="form-input" value={clearDate} onChange={e => setClearDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Comments</label>
              <textarea className="form-input" rows={2} value={clearComments} onChange={e => setClearComments(e.target.value)} />
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" onClick={() => setShowClear(false)} disabled={busy}>Cancel</button>
            <button className="btn btn-primary" onClick={doClear} disabled={busy || !clearDate}>Confirm Clear</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
