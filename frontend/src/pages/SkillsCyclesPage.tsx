import { useEffect, useState, useCallback } from 'react';
import { skillsService, type CyclePayload } from '../services/skillsService';
import { storage } from '../utils/storage';
import type { CycleRow } from '../types';
import { stateBadgeClass, stateLabel, formatDate } from '../utils/skills';
import Icon from '../components/Icon';

const emptyForm: CyclePayload = {
  cycle_id: '', period_start: '', period_end: '',
  employee_due: '', manager_due: '', closure_target: '', notes: '',
};

export default function SkillsCyclesPage() {
  const [cycles, setCycles] = useState<CycleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const [editId, setEditId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CyclePayload>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState('');

  // export
  const [expStatus, setExpStatus] = useState('all');
  const [expCycle, setExpCycle] = useState('');
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setCycles((await skillsService.cycles()).cycles); }
    catch { setError('Failed to load review cycles.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  function openCreate() { setForm(emptyForm); setEditId(null); setFormErr(''); setShowForm(true); setMsg(''); }
  function openEdit(c: CycleRow) {
    setForm({
      cycle_id: c.cycle_id, period_start: c.period_start.slice(0, 10), period_end: c.period_end.slice(0, 10),
      employee_due: c.employee_due.slice(0, 10), manager_due: c.manager_due.slice(0, 10),
      closure_target: c.closure_target.slice(0, 10), notes: c.notes || '',
    });
    setEditId(c.id); setFormErr(''); setShowForm(true); setMsg('');
  }

  const set = (k: keyof CyclePayload) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setFormErr('');
    for (const k of ['cycle_id', 'period_start', 'period_end', 'employee_due', 'manager_due', 'closure_target'] as const) {
      if (!form[k]) { setFormErr('All fields except notes are required.'); return; }
    }
    setBusy(true);
    try {
      if (editId) { await skillsService.updateCycle(editId, form); setMsg('Cycle updated.'); }
      else { await skillsService.createCycle(form); setMsg('Cycle created.'); }
      setShowForm(false);
      await load();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: Record<string, string[] | string> } };
      const d = ax.response?.data;
      const first = d ? Object.values(d)[0] : null;
      setFormErr(Array.isArray(first) ? first[0] : (first as string) || 'Could not save the cycle.');
    } finally { setBusy(false); }
  }

  async function remove(c: CycleRow) {
    if (!confirm(`Delete cycle "${c.cycle_id}"? Submissions for it will also be removed.`)) return;
    try { await skillsService.deleteCycle(c.id); setMsg('Cycle deleted.'); await load(); }
    catch { setError('Delete failed.'); }
  }

  async function exportXlsx() {
    setExporting(true); setError('');
    try {
      const token = storage.getAccessToken();
      const resp = await fetch(skillsService.exportUrl({ status: expStatus, cycle: expCycle || undefined }), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setError('Export failed.'); return; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `JSAN_QF09_Skill_Matrix_${expCycle || 'all-cycles'}_${expStatus}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { setError('Export failed.'); }
    finally { setExporting(false); }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Review Cycles</h1>
          <p className="page-subtitle">Manage the six-month review calendar and export the skill matrix</p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}><Icon name="plus" size={16} /> Add Cycle</button>
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Export panel */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h-flex"><h3>Export Skill Matrix</h3></div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Status</label>
            <select className="form-input" value={expStatus} onChange={e => setExpStatus(e.target.value)}>
              <option value="all">All (everyone)</option>
              <option value="submitted">Submitted</option>
              <option value="draft">Draft</option>
              <option value="approved">Recorded</option>
              <option value="rejected">Needs update</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Cycle</label>
            <select className="form-input" value={expCycle} onChange={e => setExpCycle(e.target.value)}>
              <option value="">All cycles</option>
              {cycles.map(c => <option key={c.cycle_id} value={c.cycle_id}>{c.cycle_id}</option>)}
            </select>
          </div>
          <button className="btn btn-secondary" onClick={exportXlsx} disabled={exporting}>
            {exporting ? 'Exporting…' : <><Icon name="file" size={15} /> Download Excel</>}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : (
        <div className="card">
          <table className="kt-table">
            <thead><tr><th>Cycle</th><th>Period</th><th>Employee Due</th><th>Manager Due</th><th>Closes</th><th>State</th><th></th></tr></thead>
            <tbody>
              {cycles.map(c => (
                <tr key={c.cycle_id} style={c.is_active ? { background: 'var(--primary-light)' } : undefined}>
                  <td><b>{c.cycle_id}</b>{c.is_active && <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>active</span>}</td>
                  <td>{formatDate(c.period_start)} – {formatDate(c.period_end)}</td>
                  <td>{formatDate(c.employee_due)}</td>
                  <td>{formatDate(c.manager_due)}</td>
                  <td>{formatDate(c.closure_target)}</td>
                  <td><span className={`badge ${stateBadgeClass(c.state)}`}>{stateLabel(c.state)}</span></td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(c)}>Edit</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => remove(c)}>Delete</button>
                  </td>
                </tr>
              ))}
              {cycles.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 24 }}>No review cycles yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={() => !busy && setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header"><h3>{editId ? 'Edit Review Cycle' : 'Add Review Cycle'}</h3></div>
            <form onSubmit={save}>
              <div className="modal-body">
                {formErr && <div className="error-message" style={{ marginBottom: 12 }}>{formErr}</div>}
                <div className="form-group">
                  <label className="form-label">Cycle ID *</label>
                  <input className="form-input" value={form.cycle_id} onChange={set('cycle_id')} placeholder="e.g. 2027-H1" disabled={!!editId} />
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Period Start *</label>
                    <input type="date" className="form-input" value={form.period_start} onChange={set('period_start')} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Period End *</label>
                    <input type="date" className="form-input" value={form.period_end} onChange={set('period_end')} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Employee Due *</label>
                    <input type="date" className="form-input" value={form.employee_due} onChange={set('employee_due')} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Manager Due *</label>
                    <input type="date" className="form-input" value={form.manager_due} onChange={set('manager_due')} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Closure Target *</label>
                    <input type="date" className="form-input" value={form.closure_target} onChange={set('closure_target')} />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Notes</label>
                  <textarea className="form-input" rows={2} value={form.notes} onChange={set('notes')} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)} disabled={busy}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : (editId ? 'Save' : 'Create')}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
