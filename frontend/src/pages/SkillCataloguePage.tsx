import { useEffect, useState, useCallback } from 'react';
import { skillsService } from '../services/skillsService';
import type { CatalogueSkill } from '../types';
import Icon from '../components/Icon';

export default function SkillCataloguePage() {
  const [skills, setSkills] = useState<CatalogueSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState('');
  const [tools, setTools] = useState('');
  const [customers, setCustomers] = useState('');
  const [busy, setBusy] = useState(false);
  const [addErr, setAddErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try { setSkills((await skillsService.catalogue()).skills); }
    catch { setError('Failed to load the catalogue.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setAddErr('');
    if (!name.trim()) { setAddErr('Enter a skill name.'); return; }
    setBusy(true);
    try {
      await skillsService.addCatalogue({ name: name.trim(), tools, customers });
      setShowAdd(false); setName(''); setTools(''); setCustomers('');
      setMsg('Skill added to the catalogue.');
      await load();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setAddErr(ax.response?.data?.detail || 'Could not add skill.');
    } finally { setBusy(false); }
  }

  async function toggle(s: CatalogueSkill) {
    try { await skillsService.updateCatalogue(s.id, { active: !s.active }); await load(); }
    catch { setError('Update failed.'); }
  }

  async function remove(s: CatalogueSkill) {
    if (!confirm(`Delete "${s.name}" from the catalogue? History is not affected.`)) return;
    try { await skillsService.deleteCatalogue(s.id); setMsg('Skill deleted.'); await load(); }
    catch { setError('Delete failed.'); }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Skill Catalogue</h1>
          <p className="page-subtitle">Skills employees pick from and Team filters on</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setShowAdd(true); setMsg(''); }}>
          <Icon name="plus" size={16} /> Add Skill
        </button>
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : (
        <div className="card">
          <table className="kt-table">
            <thead><tr><th>Skill</th><th>Typical tools</th><th>Customers</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {skills.map(s => (
                <tr key={s.id}>
                  <td><b>{s.name}</b></td>
                  <td>{s.tools.join(', ') || '—'}</td>
                  <td>{s.customers.join(', ') || '—'}</td>
                  <td><span className={`badge ${s.active ? 'badge-active' : 'badge-exited'}`}>{s.active ? 'Active' : 'Hidden'}</span></td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => toggle(s)}>{s.active ? 'Hide' : 'Show'}</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => remove(s)}>Delete</button>
                  </td>
                </tr>
              ))}
              {skills.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: 'center', padding: 24 }}>No skills in the catalogue yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <div className="modal-overlay" onClick={() => !busy && setShowAdd(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="modal-header"><h3>Add Catalogue Skill</h3></div>
            <form onSubmit={add}>
              <div className="modal-body">
                {addErr && <div className="error-message" style={{ marginBottom: 12 }}>{addErr}</div>}
                <div className="form-group">
                  <label className="form-label">Skill name *</label>
                  <input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. GIS Mapping" />
                </div>
                <div className="form-group">
                  <label className="form-label">Typical tools <span style={{ color: 'var(--text-muted)' }}>(comma-separated)</span></label>
                  <input className="form-input" value={tools} onChange={e => setTools(e.target.value)} placeholder="ArcGIS, QGIS" />
                </div>
                <div className="form-group">
                  <label className="form-label">Customers / projects <span style={{ color: 'var(--text-muted)' }}>(comma-separated)</span></label>
                  <input className="form-input" value={customers} onChange={e => setCustomers(e.target.value)} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowAdd(false)} disabled={busy}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Adding…' : 'Add'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
