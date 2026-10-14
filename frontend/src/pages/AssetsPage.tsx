import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import { clearanceService, type AssetImportResult } from '../services/clearanceService';
import { employeeService } from '../services/employeeService';
import type { Asset, AssetType, AssetCondition, EmployeeListItem } from '../types';
import { ASSET_STATUS_BADGE, ASSET_TYPES, ASSET_CONDITIONS } from '../utils/clearance';
import { ktErrorMessage } from '../utils/kt';
import Icon from '../components/Icon';

const emptyForm = {
  asset_id: '', asset_type: 'LAPTOP' as AssetType, asset_name: '',
  serial_number: '', description: '', assigned_to: '' as number | '',
  assigned_date: '', condition: '' as string, remarks: '',
};

export default function AssetsPage() {
  const { user } = useAuthContext();
  const canManage = user?.role === 'IT' || user?.role === 'ADMIN';
  const isPrivileged = ['IT', 'ADMIN', 'HR', 'FINANCE', 'MANAGER'].includes(user?.role ?? '');

  const [assets, setAssets] = useState<Asset[]>([]);
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Asset | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<AssetImportResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const filters: Record<string, string> = {};
      if (typeFilter) filters.asset_type = typeFilter;
      if (statusFilter) filters.status = statusFilter;
      if (search) filters.search = search;
      const data = await clearanceService.listAssets(filters);
      setAssets(data);
    } catch {
      setError('Failed to load assets.');
    } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter, search]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (canManage) {
      employeeService.getEmployees({ page_size: 200 })
        .then(r => setEmployees(r.results))
        .catch(() => setError('Could not load the employee list for assignment.'));
    }
  }, [canManage]);

  function openCreate() {
    setEditing(null); setForm(emptyForm); setFormError(''); setShowForm(true);
  }
  function openEdit(a: Asset) {
    setEditing(a);
    setForm({
      asset_id: a.asset_id, asset_type: a.asset_type, asset_name: a.asset_name,
      serial_number: a.serial_number, description: a.description,
      assigned_to: a.assigned_to ?? '', assigned_date: a.assigned_date ?? '',
      condition: a.condition, remarks: a.remarks,
    });
    setFormError(''); setShowForm(true);
  }

  async function save() {
    setBusy(true); setFormError('');
    try {
      const payload = {
        asset_type: form.asset_type, asset_name: form.asset_name,
        serial_number: form.serial_number, description: form.description,
        assigned_to: form.assigned_to === '' ? null : Number(form.assigned_to),
        assigned_date: form.assigned_date || null,
        condition: form.condition as AssetCondition | '', remarks: form.remarks,
      };
      if (editing) {
        await clearanceService.updateAsset(editing.id, payload);
        setMsg('Asset updated.');
      } else {
        await clearanceService.createAsset({ ...payload, asset_id: form.asset_id });
        setMsg('Asset created.');
      }
      setShowForm(false);
      await load();
    } catch (err) {
      setFormError(ktErrorMessage(err, 'Failed to save asset.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';  // allow re-selecting the same file later
    if (!file) return;
    setImporting(true); setError(''); setMsg(''); setImportResult(null);
    try {
      const result = await clearanceService.importAssets(file);
      setImportResult(result);
      setMsg(`Import finished: ${result.created} created, ${result.skipped} skipped${result.errors.length ? `, ${result.errors.length} row(s) with errors` : ''}.`);
      await load();
    } catch (err) {
      setError(ktErrorMessage(err, 'Failed to import assets.'));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{isPrivileged ? 'Assets' : 'My Assets'}</h1>
          <p className="page-subtitle">{isPrivileged ? 'Company asset catalogue and assignments.' : 'Assets currently assigned to you.'}</p>
        </div>
        {canManage && (
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              style={{ display: 'none' }}
              onChange={handleImportFile}
            />
            <button
              className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
              title={'CSV columns: asset_id (required), asset_name (required), asset_type, '
                + 'serial_number, description, assigned_to_employee_id, assigned_date (YYYY-MM-DD), '
                + 'condition, remarks. Rows with an existing asset_id are skipped.'}
            >
              {importing ? <><span className="btn-spinner" /> Importing…</> : 'Import CSV'}
            </button>
            <button className="btn btn-primary" onClick={openCreate}>+ New Asset</button>
          </div>
        )}
      </div>

      {msg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{msg}</div>}
      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      {importResult && importResult.errors.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h4 style={{ margin: 0 }}>Rows that could not be imported ({importResult.errors.length})</h4>
            <button className="btn btn-ghost" onClick={() => setImportResult(null)}>Dismiss</button>
          </div>
          <table className="table" style={{ marginTop: 12 }}>
            <thead><tr><th>Row</th><th>Asset ID</th><th>Reason</th></tr></thead>
            <tbody>
              {importResult.errors.map((er, i) => (
                <tr key={i}><td>{er.row}</td><td>{er.asset_id || '—'}</td><td>{er.message}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isPrivileged && (
        <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Search</label>
            <input className="form-input" placeholder="ID / serial / name…" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Type</label>
            <select className="form-input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
              <option value="">All</option>
              {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Status</label>
            <select className="form-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="RETURN_PENDING">Return Pending</option>
              <option value="RETURNED">Returned</option>
              <option value="CLEARED">Cleared</option>
              <option value="DAMAGED">Damaged</option>
              <option value="LOST">Lost</option>
            </select>
          </div>
        </div>
      )}

      <div className="card">
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
        ) : assets.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="laptop" size={40} /></div><h3>No assets</h3>
            <p style={{ color: 'var(--text-secondary)' }}>{isPrivileged ? 'No assets match your filters.' : 'You have no assigned assets.'}</p>
          </div>
        ) : (
          <table className="kt-table">
            <thead>
              <tr>
                <th>Asset ID</th><th>Type</th><th>Name</th><th>Serial</th>
                {isPrivileged && <th>Assigned To</th>}<th>Status</th>
                {canManage && <th></th>}
              </tr>
            </thead>
            <tbody>
              {assets.map(a => (
                <tr key={a.id}>
                  <td>{a.asset_id}</td>
                  <td>{a.asset_type_display}</td>
                  <td>{a.asset_name}</td>
                  <td>{a.serial_number || '—'}</td>
                  {isPrivileged && <td>{a.assigned_to_name || '—'}</td>}
                  <td><span className={`badge ${ASSET_STATUS_BADGE[a.status]}`}>{a.status_display}</span></td>
                  {canManage && <td><button className="btn btn-ghost" onClick={() => openEdit(a)}>Edit</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => !busy && setShowForm(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>{editing ? 'Edit Asset' : 'New Asset'}</h3></div>
            <div className="modal-body" style={{ maxHeight: '65vh', overflowY: 'auto' }}>
              {formError && <div className="error-message" style={{ marginBottom: 12 }}>{formError}</div>}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Asset ID <span style={{ color: 'var(--danger)' }}>*</span></label>
                  <input className="form-input" value={form.asset_id} disabled={!!editing}
                    onChange={e => setForm(f => ({ ...f, asset_id: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Type</label>
                  <select className="form-input" value={form.asset_type} onChange={e => setForm(f => ({ ...f, asset_type: e.target.value as AssetType }))}>
                    {ASSET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Name <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input className="form-input" value={form.asset_name} onChange={e => setForm(f => ({ ...f, asset_name: e.target.value }))} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Serial Number</label>
                  <input className="form-input" value={form.serial_number} onChange={e => setForm(f => ({ ...f, serial_number: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Condition</label>
                  <select className="form-input" value={form.condition} onChange={e => setForm(f => ({ ...f, condition: e.target.value }))}>
                    <option value="">—</option>
                    {ASSET_CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Assigned To</label>
                  <select className="form-input" value={form.assigned_to} onChange={e => setForm(f => ({ ...f, assigned_to: e.target.value ? Number(e.target.value) : '' }))}>
                    <option value="">— Unassigned —</option>
                    {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.first_name} {emp.last_name} ({emp.employee_id})</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Assigned Date</label>
                  <input type="date" className="form-input" value={form.assigned_date} onChange={e => setForm(f => ({ ...f, assigned_date: e.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea className="form-input" rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Assigned date is optional and never auto-filled.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowForm(false)} disabled={busy}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={busy || !form.asset_name.trim() || (!editing && !form.asset_id.trim())}>
                {busy ? <><span className="btn-spinner" /> Saving…</> : editing ? 'Save' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
