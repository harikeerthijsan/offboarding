import { useEffect, useState, useCallback } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import { policyService } from '../services/policyService';
import { storage } from '../utils/storage';
import type { Policy } from '../types';
import Icon from '../components/Icon';

const CATEGORIES = [
  { value: 'HR', label: 'HR' },
  { value: 'IT', label: 'IT' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'SECURITY', label: 'Security' },
  { value: 'CODE_OF_CONDUCT', label: 'Code of Conduct' },
  { value: 'LEAVE', label: 'Leave & Attendance' },
  { value: 'OTHER', label: 'Other' },
];

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  try {
    // Date-only strings (YYYY-MM-DD) must be parsed as local, not UTC,
    // otherwise toLocaleDateString shifts them a day in non-UTC timezones.
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
    const date = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(d);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }
  catch { return d; }
}
function formatSize(bytes: number | null) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PoliciesPage() {
  const { user } = useAuthContext();
  const canManage = user?.role === 'HR' || user?.role === 'ADMIN';

  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [search, setSearch] = useState('');

  // upload modal
  const [showUpload, setShowUpload] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('OTHER');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadErr, setUploadErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await policyService.list({
        category: catFilter || undefined,
        search: search || undefined,
      });
      setPolicies(data);
    } catch {
      setError('Failed to load policies.');
    } finally {
      setLoading(false);
    }
  }, [catFilter, search]);

  useEffect(() => { load(); }, [load]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setUploadErr('');
    if (!title.trim()) { setUploadErr('Please enter a title.'); return; }
    if (!file) { setUploadErr('Please choose a file to upload.'); return; }
    setBusy(true);
    try {
      await policyService.upload({ title: title.trim(), description, category, file });
      setShowUpload(false);
      setTitle(''); setDescription(''); setCategory('OTHER'); setFile(null);
      setMsg('Policy uploaded successfully.');
      await load();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: Record<string, string[] | string> } };
      const data = ax.response?.data;
      const firstErr = data ? Object.values(data)[0] : null;
      setUploadErr(Array.isArray(firstErr) ? firstErr[0] : (firstErr as string) || 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }

  async function view(p: Policy) {
    try {
      const token = storage.getAccessToken();
      const resp = await fetch(policyService.downloadUrl(p.id), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setError('You are not permitted to open this document.'); return; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch { setError('Could not open the document.'); }
  }

  async function toggleActive(p: Policy) {
    try {
      await policyService.update(p.id, { is_active: !p.is_active });
      await load();
    } catch { setError('Update failed.'); }
  }

  async function remove(p: Policy) {
    if (!confirm(`Delete "${p.title}"? This cannot be undone.`)) return;
    try {
      await policyService.remove(p.id);
      setMsg('Policy deleted.');
      await load();
    } catch { setError('Delete failed.'); }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Policies</h1>
          <p className="page-subtitle">Company policy documents{canManage ? ' — upload and manage' : ''}</p>
        </div>
        {canManage && (
          <button className="btn btn-primary" onClick={() => { setShowUpload(true); setMsg(''); }}>
            <Icon name="plus" size={16} /> Upload Policy
          </button>
        )}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="filters-bar" style={{ marginBottom: 16 }}>
        <input className="search-input" placeholder="Search policies…" value={search}
          onChange={e => setSearch(e.target.value)} />
        <select className="filter-select" value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : policies.length === 0 ? (
        <div className="card"><div className="empty-state" style={{ textAlign: 'center', padding: 40 }}>
          <div className="empty-icon"><Icon name="file" size={40} /></div>
          <h3>No policies yet</h3>
          <p style={{ color: 'var(--text-secondary)' }}>
            {canManage ? 'Upload the first company policy document.' : 'No policy documents have been published yet.'}
          </p>
        </div></div>
      ) : (
        <div className="policy-grid">
          {policies.map(p => (
            <div className="card policy-card" key={p.id}>
              <div className="policy-card-top">
                <span className="policy-ic"><Icon name="file" size={20} /></span>
                <span className="badge badge-it">{p.category_display}</span>
                {!p.is_active && <span className="badge badge-exited">Archived</span>}
              </div>
              <h3 className="policy-title">{p.title}</h3>
              {p.description && <p className="policy-desc">{p.description}</p>}
              <div className="policy-meta">
                <span>{p.file_name}</span>
                {p.file_size != null && <span> · {formatSize(p.file_size)}</span>}
              </div>
              <div className="policy-meta">
                Uploaded {formatDate(p.created_at)}{p.uploaded_by_name ? ` by ${p.uploaded_by_name}` : ''}
              </div>
              <div className="policy-actions">
                <button className="btn btn-primary btn-sm" onClick={() => view(p)}>
                  <Icon name="eye" size={15} /> View
                </button>
                {canManage && (
                  <>
                    <button className="btn btn-secondary btn-sm" onClick={() => toggleActive(p)}>
                      {p.is_active ? 'Archive' : 'Restore'}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => remove(p)}>Delete</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload modal */}
      {showUpload && (
        <div className="modal-overlay" onClick={() => !busy && setShowUpload(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header"><h3>Upload Policy Document</h3></div>
            <form onSubmit={handleUpload}>
              <div className="modal-body">
                {uploadErr && <div className="error-message" style={{ marginBottom: 12 }}>{uploadErr}</div>}
                <div className="form-group">
                  <label className="form-label">Title *</label>
                  <input className="form-input" value={title} onChange={e => setTitle(e.target.value)}
                    placeholder="e.g. Leave Policy 2026" />
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select className="form-input" value={category} onChange={e => setCategory(e.target.value)}>
                    {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea className="form-input" rows={3} value={description}
                    onChange={e => setDescription(e.target.value)} placeholder="Short summary (optional)" />
                </div>
                <div className="form-group">
                  <label className="form-label">File * <span style={{ color: 'var(--text-muted)' }}>(PDF, DOC, DOCX — max 20 MB)</span></label>
                  <input type="file" className="form-input" accept=".pdf,.doc,.docx"
                    onChange={e => setFile(e.target.files?.[0] ?? null)} />
                  {file && <span className="field-hint" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{file.name} · {formatSize(file.size)}</span>}
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowUpload(false)} disabled={busy}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? <><span className="btn-spinner" /> Uploading…</> : 'Upload'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
