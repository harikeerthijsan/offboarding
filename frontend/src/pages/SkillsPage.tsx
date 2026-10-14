import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { skillsService } from '../services/skillsService';
import type { CycleRow, SkillItem, SkillsPicker, SkillSubmission } from '../types';
import { SKILL_CATEGORIES, PROFICIENCY, SKILL_STATUSES, stateBadgeClass, stateLabel, formatDate } from '../utils/skills';
import Icon from '../components/Icon';
import '../styles/skills-form.css';

function blankRow(): SkillItem {
  return { name: '', category: 'Technical', status: 'current', proficiency: 'Intermediate', tools: [], years: null, company: '', role: '', customer: '', note: '' };
}

export default function SkillsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [profileComplete, setProfileComplete] = useState(true);
  const [cycles, setCycles] = useState<CycleRow[]>([]);
  const [picker, setPicker] = useState<SkillsPicker>({ skills: [], companies: [], roles: [] });
  const [rows, setRows] = useState<SkillItem[]>([]);
  const [note, setNote] = useState('');
  const [submission, setSubmission] = useState<SkillSubmission | null>(null);
  const [editing, setEditing] = useState(true);
  const [savedStatus, setSavedStatus] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewedBy, setReviewedBy] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const activeCycle = useMemo(() => cycles.find(c => c.is_active) || null, [cycles]);

  useEffect(() => {
    (async () => {
      try {
        const [me, pk] = await Promise.all([skillsService.me(), skillsService.picker()]);
        setProfileComplete(me.profile_complete);
        setCycles(me.cycles);
        setPicker(pk);
        const active = me.cycles.find(c => c.is_active);
        const mine = active ? me.submissions.find(s => s.cycle_id === active.cycle_id) : undefined;
        setSubmission(mine || null);
        if (mine) {
          setSavedStatus(mine.status);
          setReviewedBy(mine.reviewed_by_name || null);
          setReviewNote(mine.status === 'rejected' ? (mine.review_note || '') : '');
          if (mine.status === 'draft' || mine.status === 'rejected') {
            // resume editing a saved draft, or revise after an update request —
            // pre-fill the matrix so they can see and amend what they entered.
            setEditing(true);
            setRows(mine.skills.length ? mine.skills.map(s => ({ ...s })) : [blankRow()]);
            setNote(mine.employee_note || '');
          } else {
            // submitted / approved: show a read-only snapshot of what was submitted.
            setEditing(false);
            setRows([blankRow()]);
          }
        } else {
          setEditing(true);
          setRows([blankRow()]);
        }
      } catch {
        setError('Failed to load your skills.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const catalogueNames = useMemo(() => picker.skills.map(s => s.name), [picker]);
  const toolsFor = (name: string): string[] => picker.skills.find(s => s.name.toLowerCase() === name.toLowerCase())?.tools || [];

  function setRow(i: number, patch: Partial<SkillItem>) {
    setRows(rs => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function addRow() { setRows(rs => [...rs, blankRow()]); }
  function removeRow(i: number) { setRows(rs => rs.filter((_, idx) => idx !== i)); }

  async function save(submit: boolean) {
    setError(''); setMsg('');
    const clean = rows.filter(r => r.name.trim());
    if (submit && clean.length === 0) { setError('Add at least one skill before submitting.'); return; }
    setBusy(true);
    try {
      const { submission: saved } = await skillsService.saveSubmission(clean, submit, note);
      setSubmission(saved);
      setSavedStatus(saved.status);
      if (submit) {
        // Submitted for approval — switch to the read-only snapshot so the
        // employee can see exactly what they submitted.
        setEditing(false);
        setReviewNote('');
      } else {
        // Draft saved — keep editing, reflecting what was stored.
        setRows(saved.skills.length ? saved.skills.map(s => ({ ...s })) : [blankRow()]);
      }
      // refresh cycle states
      const me = await skillsService.me();
      setCycles(me.cycles);
      setMsg(submit ? 'Your skills were submitted for your manager’s approval.' : 'Draft saved.');
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setError(ax.response?.data?.detail || 'Could not save. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  function editSubmission() {
    if (!submission) return;
    setRows(submission.skills.length ? submission.skills.map(s => ({ ...s })) : [blankRow()]);
    setNote(submission.employee_note || '');
    setMsg(''); setError('');
    setEditing(true);
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;

  const editable = activeCycle && ['open', 'overdue', 'draft', 'submitted', 'rejected'].includes(activeCycle.state);

  return (
    <div className="skills-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">My Skills</h1>
          <p className="page-subtitle">Keep your skill matrix up to date for each review cycle</p>
        </div>
        {savedStatus && <span className={`badge ${stateBadgeClass(savedStatus)}`} style={{ fontSize: 13, padding: '6px 12px' }}>{stateLabel(savedStatus)}</span>}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      {savedStatus === 'submitted' && (
        <div className="alert" style={{ marginBottom: 16, background: '#eff6ff', color: '#1d4ed8' }}>
          Your skills are submitted and awaiting your manager’s approval.
        </div>
      )}
      {savedStatus === 'approved' && (
        <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>
          Your skills for this cycle were approved{reviewedBy ? ` by ${reviewedBy}` : ''} and are recorded.
        </div>
      )}
      {savedStatus === 'rejected' && reviewNote && (
        <div className="alert" style={{ marginBottom: 16, background: '#fffbeb', color: '#b45309' }}>
          <b>Update requested{reviewedBy ? ` by ${reviewedBy}` : ''}:</b> {reviewNote} — please update your skills and submit again.
        </div>
      )}

      {!profileComplete && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ flex: 1, color: 'var(--text-secondary)' }}>
              Complete your profile (department &amp; designation) before submitting your skills.
            </span>
            <button className="btn btn-primary" onClick={() => navigate('/profile')}>Go to Profile</button>
          </div>
        </div>
      )}

      {/* Active cycle banner */}
      <div className="card" style={{ marginBottom: 16 }}>
        {activeCycle ? (
          <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
            <div><strong style={{ fontSize: 16 }}>{activeCycle.cycle_id}</strong></div>
            <span className={`badge ${stateBadgeClass(activeCycle.state)}`}>{stateLabel(activeCycle.state)}</span>
            <span className="muted">Employee due: <b style={{ color: 'var(--text)' }}>{formatDate(activeCycle.employee_due)}</b></span>
            <span className="muted">Closes: <b style={{ color: 'var(--text)' }}>{formatDate(activeCycle.closure_target)}</b></span>
          </div>
        ) : (
          <span className="muted">No review cycle is open yet. You can still prepare your skills.</span>
        )}
      </div>

      {/* Read-only snapshot of what was submitted (submitted / approved) */}
      {!editing && submission && (
        <div className="card">
          <div className="card-h-flex">
            <h3>Your Submitted Skills</h3>
            <span className="muted">
              {submission.submitted_at ? `Submitted ${formatDate(submission.submitted_at)}` : ''}
            </span>
          </div>
          <div className="skills-editor">
            <table className="kt-table skills-table">
              <thead>
                <tr>
                  <th>Skill</th><th>Category</th><th>Status</th><th>Level</th><th>Years</th>
                  <th>Company</th><th>Role</th><th>Customer / Project</th><th>Note</th>
                </tr>
              </thead>
              <tbody>
                {submission.skills.map((s, i) => (
                  <tr key={i}>
                    <td data-label="Skill"><b>{s.name}</b></td>
                    <td data-label="Category">{s.category}</td>
                    <td data-label="Status">{SKILL_STATUSES.find(x => x.value === s.status)?.label || s.status}</td>
                    <td data-label="Level">{s.proficiency}</td>
                    <td data-label="Years">{s.years ?? '—'}</td>
                    <td data-label="Company">{s.company || '—'}</td>
                    <td data-label="Role">{s.role || '—'}</td>
                    <td data-label="Customer / Project">{s.customer || '—'}</td>
                    <td data-label="Note">{s.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {submission.employee_note && (
            <p className="muted" style={{ marginTop: 12 }}><b>Your note:</b> {submission.employee_note}</p>
          )}
          {submission.status === 'submitted' && (
            <div className="form-actions" style={{ marginTop: 12 }}>
              <button className="btn btn-secondary" onClick={editSubmission} disabled={!editable}>Edit &amp; resubmit</button>
            </div>
          )}
        </div>
      )}

      {/* Skill rows (editable) */}
      {editing && (
      <div className="card">
        <div className="card-h-flex">
          <h3>Skill Matrix</h3>
        </div>

        <div className="skills-editor">
          <table className="kt-table skills-table">
            <thead>
              <tr>
                <th>Skill</th><th>Category</th><th>Status</th><th>Level</th><th>Years</th>
                <th>Company</th><th>Role</th><th>Customer / Project</th><th>Note</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td data-label="Skill name">
                    <input aria-label={`Skill ${i + 1}: name`} className="form-input sk-in" list="sk-catalogue" value={r.name}
                      onChange={e => { const name = e.target.value; setRow(i, { name, tools: toolsFor(name) }); }}
                      placeholder="Skill name" />
                  </td>
                  <td data-label="Category">
                    <select aria-label={`Skill ${i + 1}: category`} className="form-input sk-in" value={r.category} onChange={e => setRow(i, { category: e.target.value })}>
                      {SKILL_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td data-label="Status">
                    <select aria-label={`Skill ${i + 1}: status`} className="form-input sk-in" value={r.status} onChange={e => setRow(i, { status: e.target.value })}>
                      {SKILL_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </td>
                  <td data-label="Proficiency level">
                    <select aria-label={`Skill ${i + 1}: proficiency`} className="form-input sk-in" value={r.proficiency} onChange={e => setRow(i, { proficiency: e.target.value })}>
                      {PROFICIENCY.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td data-label="Experience (years)">
                    <input aria-label={`Skill ${i + 1}: experience in years`} className="form-input sk-in sk-years" type="number" min={0} max={50} step={0.5}
                      value={r.years ?? ''} onChange={e => setRow(i, { years: e.target.value === '' ? null : Number(e.target.value) })} />
                  </td>
                  <td data-label="Company">
                    <input aria-label={`Skill ${i + 1}: company`} className="form-input sk-in" list="sk-companies" value={r.company}
                      onChange={e => setRow(i, { company: e.target.value })} />
                  </td>
                  <td data-label="Role">
                    <input aria-label={`Skill ${i + 1}: role`} className="form-input sk-in" list="sk-roles" value={r.role}
                      onChange={e => setRow(i, { role: e.target.value })} />
                  </td>
                  <td data-label="Customer / project">
                    <input aria-label={`Skill ${i + 1}: customer or project`} className="form-input sk-in" value={r.customer} onChange={e => setRow(i, { customer: e.target.value })} />
                  </td>
                  <td data-label="Skill note">
                    <input aria-label={`Skill ${i + 1}: note`} className="form-input sk-in" value={r.note} onChange={e => setRow(i, { note: e.target.value })} />
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => removeRow(i)} aria-label={`Remove skill ${i + 1}`} disabled={rows.length === 1}>Remove skill</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <datalist id="sk-catalogue">{catalogueNames.map(n => <option key={n} value={n} />)}</datalist>
        <datalist id="sk-companies">{picker.companies.map(n => <option key={n} value={n} />)}</datalist>
        <datalist id="sk-roles">{picker.roles.map(n => <option key={n} value={n} />)}</datalist>

        <button className="btn btn-secondary btn-sm" style={{ marginTop: 12 }} onClick={addRow}>
          <Icon name="plus" size={15} /> Add skill
        </button>

        <div className="form-group" style={{ marginTop: 16 }}>
          <label className="form-label">Note (optional)</label>
          <textarea className="form-input" rows={2} value={note} onChange={e => setNote(e.target.value)}
            placeholder="Anything your manager should know…" maxLength={1000} />
        </div>

        <div className="form-actions" style={{ marginTop: 8 }}>
          <button className="btn btn-secondary" onClick={() => save(false)} disabled={busy || !profileComplete || savedStatus === 'approved'}>
            {busy ? 'Saving…' : 'Save Draft'}
          </button>
          <button className="btn btn-primary" onClick={() => save(true)} disabled={busy || !profileComplete || !editable}>
            {busy ? 'Saving…' : 'Submit'}
          </button>
        </div>
      </div>
      )}

      {/* Review timeline */}
      {cycles.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginBottom: 14 }}>Review Timeline</h3>
          <table className="kt-table">
            <thead><tr><th>Cycle</th><th>Period</th><th>Employee Due</th><th>Status</th></tr></thead>
            <tbody>
              {cycles.map(c => (
                <tr key={c.cycle_id} style={c.is_active ? { background: 'var(--primary-light)' } : undefined}>
                  <td><b>{c.cycle_id}</b>{c.is_active && <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>active</span>}</td>
                  <td>{formatDate(c.period_start)} – {formatDate(c.period_end)}</td>
                  <td>{formatDate(c.employee_due)}</td>
                  <td><span className={`badge ${stateBadgeClass(c.state)}`}>{stateLabel(c.state)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
