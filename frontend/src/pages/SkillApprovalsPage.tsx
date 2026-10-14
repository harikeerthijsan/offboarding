import { useEffect, useState } from 'react';
import { skillsService } from '../services/skillsService';
import type { SkillApproval } from '../types';
import { formatDate } from '../utils/skills';
import Icon from '../components/Icon';

export default function SkillApprovalsPage() {
  const [rows, setRows] = useState<SkillApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [note, setNote] = useState('');

  async function load() {
    setLoading(true); setError('');
    try {
      const { approvals } = await skillsService.approvals();
      setRows(approvals);
    } catch {
      setError('Failed to load pending approvals.');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function review(id: number, action: 'approve' | 'reject', reviewNote = '') {
    setBusyId(id); setError(''); setMsg('');
    try {
      await skillsService.reviewSubmission(id, action, reviewNote);
      setRows(rs => rs.filter(r => r.id !== id));
      setRejectId(null); setNote('');
      setMsg(action === 'approve' ? 'Skills approved.' : 'Update requested — the employee has been notified.');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax.response?.data?.detail || 'Could not submit your review. Please try again.');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Skill Approvals</h1>
          <p className="page-subtitle">Review and approve the skill submissions awaiting you</p>
        </div>
        <span className="muted">{rows.length} pending</span>
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : rows.length === 0 ? (
        <div className="card"><p className="muted" style={{ textAlign: 'center', padding: 24 }}>Nothing awaiting your approval.</p></div>
      ) : (
        rows.map(r => (
          <div className="card" key={r.id} style={{ marginBottom: 16 }}>
            <div className="card-h-flex">
              <div>
                <h3 style={{ marginBottom: 4 }}>{r.employee_name} {r.employee_id && <code style={{ fontSize: 12, marginLeft: 6 }}>{r.employee_id}</code>}</h3>
                <span className="muted">
                  {[r.designation, r.department].filter(Boolean).join(' · ')}
                  {' · '}{r.cycle_id}{' · submitted '}{formatDate(r.submitted_at)}
                </span>
              </div>
            </div>

            <div className="skills-editor" style={{ marginTop: 12 }}>
              <table className="kt-table skills-table">
                <thead>
                  <tr><th>Skill</th><th>Category</th><th>Level</th><th>Years</th><th>Company</th><th>Role</th><th>Customer / Project</th></tr>
                </thead>
                <tbody>
                  {r.skills.map((s, i) => (
                    <tr key={i}>
                      <td>{s.name}</td><td>{s.category}</td><td>{s.proficiency}</td>
                      <td>{s.years ?? '—'}</td><td>{s.company || '—'}</td><td>{s.role || '—'}</td><td>{s.customer || '—'}</td>
                    </tr>
                  ))}
                  {r.skills.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: 'center' }}>No skills listed.</td></tr>}
                </tbody>
              </table>
            </div>

            {r.employee_note && <p className="muted" style={{ marginTop: 10 }}><b>Employee note:</b> {r.employee_note}</p>}

            {rejectId === r.id ? (
              <div className="form-group" style={{ marginTop: 12 }}>
                <label className="form-label">What should the employee update?</label>
                <textarea className="form-input" rows={2} value={note} maxLength={1000}
                  onChange={e => setNote(e.target.value)} placeholder="Explain what needs changing…" />
                <div className="form-actions" style={{ marginTop: 8 }}>
                  <button className="btn btn-secondary" onClick={() => { setRejectId(null); setNote(''); }} disabled={busyId === r.id}>Cancel</button>
                  <button className="btn btn-primary" onClick={() => review(r.id, 'reject', note)} disabled={busyId === r.id || !note.trim()}>
                    {busyId === r.id ? 'Sending…' : 'Send request'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="form-actions" style={{ marginTop: 12 }}>
                <button className="btn btn-secondary" onClick={() => { setRejectId(r.id); setNote(''); }} disabled={busyId === r.id}>
                  Request update
                </button>
                <button className="btn btn-primary" onClick={() => review(r.id, 'approve')} disabled={busyId === r.id}>
                  {busyId === r.id ? 'Saving…' : <><Icon name="check" size={15} /> Approve</>}
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
