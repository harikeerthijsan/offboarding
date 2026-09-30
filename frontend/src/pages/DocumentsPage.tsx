import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { documentService } from '../services/documentService';
import { storage } from '../utils/storage';
import type { OffboardingDocument, DocumentType, DocumentStatus, ResignationRequest } from '../types';
import { formatDate, ktErrorMessage } from '../utils/kt';
import Icon from '../components/Icon';

const STATUS_BADGE: Record<DocumentStatus, string> = {
  DRAFT: 'badge-doc-draft',
  GENERATED: 'badge-doc-generated',
  UNDER_REVIEW: 'badge-doc-under-review',
  APPROVED: 'badge-doc-approved',
  RELEASED: 'badge-doc-released',
  REVOKED: 'badge-doc-revoked',
};

const DOC_TYPES: { value: DocumentType; label: string }[] = [
  { value: 'RELIEVING_LETTER', label: 'Relieving Letter' },
  { value: 'EXPERIENCE_LETTER', label: 'Experience Letter' },
  { value: 'FULL_FINAL_SETTLEMENT', label: 'Full & Final Settlement' },
  { value: 'EXIT_CLEARANCE', label: 'Exit Clearance Certificate' },
  { value: 'OTHER', label: 'Other' },
];

export default function DocumentsPage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [docs, setDocs] = useState<OffboardingDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  const [showGen, setShowGen] = useState(false);
  const [genType, setGenType] = useState<DocumentType>('RELIEVING_LETTER');
  const [genDate, setGenDate] = useState('');

  const isHR = user?.role === 'HR' || user?.role === 'ADMIN';
  const isFinance = user?.role === 'FINANCE';
  const canGenerate = isHR || isFinance;

  const load = useCallback(async () => {
    setDocs(await documentService.list(oid));
  }, [oid]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        setResignation(await offboardingService.getResignation(oid));
        await load();
      } catch { setError('Failed to load documents.'); }
      finally { setLoading(false); }
    })();
    // eslint-disable-next-line
  }, [oid]);

  async function handleGenerate() {
    setBusy(true); setActionError('');
    try {
      await documentService.generate(oid, genType, genDate || null);
      setShowGen(false); setGenDate(''); setMsg('Document generated.');
      await load();
    } catch (err) { setActionError(ktErrorMessage(err, 'Failed to generate document.')); }
    finally { setBusy(false); }
  }

  async function act(doc: OffboardingDocument, action: 'submit_review' | 'approve' | 'reject' | 'release' | 'revoke' | 'regenerate') {
    let reason = '';
    let docDate: string | null = null;
    if (action === 'reject') { reason = prompt('Reason for rejection:') || ''; if (!reason.trim()) return; }
    if (action === 'revoke') { reason = prompt('Reason for revocation:') || ''; if (!reason.trim()) return; }
    if (action === 'regenerate') { docDate = prompt('Document date for the new version (YYYY-MM-DD, optional):') || null; }
    setBusy(true); setActionError('');
    try {
      await documentService.action(doc.id, action, { reason, document_date: docDate });
      setMsg('Done.');
      await load();
    } catch (err) { setActionError(ktErrorMessage(err, 'Action failed.')); }
    finally { setBusy(false); }
  }

  async function download(doc: OffboardingDocument) {
    // Authenticated fetch → blob (avoids exposing a public URL and carries the JWT).
    try {
      const token = storage.getAccessToken();
      const resp = await fetch(documentService.downloadUrl(doc.id), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setActionError('You are not permitted to download this document.'); return; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${doc.document_number}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { setActionError('Download failed.'); }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${oid}`)} style={{ marginBottom: 8 }}>← Back</button>
          <h1 className="page-title">Exit Documents</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {canGenerate && <button className="btn btn-primary" onClick={() => setShowGen(true)}>+ Generate Document</button>}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      <div className="card">
        {docs.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="file" size={40} /></div><h3>No documents</h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              {canGenerate ? 'Generate exit documents for this employee.' : 'No documents have been released to you yet.'}
            </p>
          </div>
        ) : (
          <table className="kt-table">
            <thead>
              <tr><th>Number</th><th>Type</th><th>Ver</th><th>Date</th><th>Status</th><th>Prepared By</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {docs.map(d => (
                <tr key={d.id}>
                  <td>{d.document_number}</td>
                  <td>{d.document_type_display}</td>
                  <td>v{d.version}</td>
                  <td>{d.document_date ? formatDate(d.document_date) : 'Not entered'}</td>
                  <td><span className={`badge ${STATUS_BADGE[d.status]}`}>{d.status_display}</span></td>
                  <td>{d.prepared_by_name || '—'}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {isHR && d.status !== 'RELEASED' && d.status !== 'REVOKED' && (
                      <button className="btn btn-ghost" onClick={() => download(d)}>Preview</button>
                    )}
                    {isHR && d.status === 'GENERATED' && (
                      <>
                        <button className="btn btn-ghost" onClick={() => act(d, 'submit_review')}>Submit</button>
                        <button className="btn btn-ghost" onClick={() => act(d, 'approve')}>Approve</button>
                        <button className="btn btn-ghost" onClick={() => act(d, 'reject')}>Reject</button>
                      </>
                    )}
                    {isHR && d.status === 'UNDER_REVIEW' && (
                      <>
                        <button className="btn btn-ghost" onClick={() => act(d, 'approve')}>Approve</button>
                        <button className="btn btn-ghost" onClick={() => act(d, 'reject')}>Reject</button>
                      </>
                    )}
                    {isHR && d.status === 'APPROVED' && (
                      <button className="btn btn-ghost" onClick={() => act(d, 'release')}>Release</button>
                    )}
                    {isHR && d.status === 'RELEASED' && (
                      <button className="btn btn-ghost" onClick={() => act(d, 'revoke')}>Revoke</button>
                    )}
                    {isHR && (d.status === 'GENERATED' || d.status === 'REVOKED') && (
                      <button className="btn btn-ghost" onClick={() => act(d, 'regenerate')}>Regenerate</button>
                    )}
                    {d.download_url && (
                      <button className="btn btn-ghost" onClick={() => download(d)}>Download</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Generate modal */}
      {showGen && (
        <div className="modal-overlay" onClick={() => !busy && setShowGen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3>Generate Document</h3></div>
            <div className="modal-body">
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <div className="form-group">
                <label className="form-label">Document Type</label>
                <select className="form-input" value={genType} onChange={e => setGenType(e.target.value as DocumentType)}>
                  {DOC_TYPES.filter(t => !isFinance || t.value === 'FULL_FINAL_SETTLEMENT').map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Document Date</label>
                <input type="date" className="form-input" value={genDate} onChange={e => setGenDate(e.target.value)} />
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>Optional and never auto-filled. Leave blank to enter later.</p>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowGen(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={busy}>Generate</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
