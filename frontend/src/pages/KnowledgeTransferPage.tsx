import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import { ktService, type KTCreatePayload } from '../services/ktService';
import { employeeService } from '../services/employeeService';
import KTDetailModal from '../components/KTDetailModal';
import type {
  KTListItem, KTSummary, Project, EmployeeListItem, ResignationRequest, KTPriority,
} from '../types';
import { KT_STATUS_BADGE, KT_PRIORITY_BADGE, formatDate, ktErrorMessage } from '../utils/kt';
import Icon from '../components/Icon';

const PRIORITIES: KTPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export default function KnowledgeTransferPage() {
  const { id } = useParams<{ id: string }>();
  const oid = Number(id);
  const { user } = useAuthContext();
  const navigate = useNavigate();

  const [resignation, setResignation] = useState<ResignationRequest | null>(null);
  const [items, setItems] = useState<KTListItem[]>([]);
  const [summary, setSummary] = useState<KTSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [actionError, setActionError] = useState('');

  // filters
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [search, setSearch] = useState('');

  // create modal
  const [showCreate, setShowCreate] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<KTCreatePayload>({
    title: '', description: '', project: null, responsibility: '',
    receiver: 0, priority: 'MEDIUM', start_date: '', target_completion_date: '',
  });

  const [detailId, setDetailId] = useState<number | null>(null);

  const canManage = user?.role === 'MANAGER' || user?.role === 'HR' || user?.role === 'ADMIN';

  const loadList = useCallback(async () => {
    const filters: Record<string, string> = {};
    if (statusFilter) filters.status = statusFilter;
    if (priorityFilter) filters.priority = priorityFilter;
    if (search) filters.search = search;
    const [list, sum] = await Promise.all([
      ktService.list(oid, filters),
      ktService.summary(oid),
    ]);
    setItems(list);
    setSummary(sum);
  }, [oid, statusFilter, priorityFilter, search]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await offboardingService.getResignation(oid);
        setResignation(res);
        await loadList();
      } catch {
        setError('Failed to load knowledge transfer.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, [oid]);

  useEffect(() => {
    if (!loading) loadList().catch(() => {});
    // eslint-disable-next-line
  }, [statusFilter, priorityFilter, search]);

  async function openCreate() {
    setActionError('');
    try {
      const [projs, emps] = await Promise.all([
        ktService.listProjects(true),
        employeeService.getEmployees({ status: 'ACTIVE', page_size: 200 }),
      ]);
      setProjects(projs);
      // Exclude the offboarding employee (compared by unique employee_id code)
      setEmployees(emps.results.filter(e => e.employee_id !== resignation?.employee_id));
    } catch {
      // still allow opening; dropdowns may be empty
    }
    setForm({
      title: '', description: '', project: null, responsibility: '',
      receiver: 0, priority: 'MEDIUM', start_date: '', target_completion_date: '',
    });
    setShowCreate(true);
  }

  async function handleCreate() {
    setCreating(true); setActionError('');
    try {
      const payload: KTCreatePayload = {
        ...form,
        project: form.project || null,
        start_date: form.start_date || null,
        target_completion_date: form.target_completion_date || null,
      };
      await ktService.create(oid, payload);
      setShowCreate(false);
      setActionMsg('Knowledge transfer task created.');
      await loadList();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Failed to create KT task.'));
    } finally {
      setCreating(false);
    }
  }

  async function handleMarkComplete() {
    if (!confirm('Mark knowledge transfer complete for this employee?\n\nAll KT tasks must already be completed.')) return;
    setActionError(''); setActionMsg('');
    try {
      await ktService.markPhaseComplete(oid);
      setActionMsg('Knowledge transfer marked complete.');
      await loadList();
    } catch (err) {
      setActionError(ktErrorMessage(err, 'Could not mark KT complete.'));
    }
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;
  if (!resignation) return null;

  const completedPct = summary && summary.total > 0 ? Math.round((summary.completed / summary.total) * 100) : 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${oid}`)} style={{ marginBottom: 8 }}>← Back</button>
          <h1 className="page-title">Knowledge Transfer</h1>
          <p className="page-subtitle">{resignation.employee_name} · {resignation.department_name}</p>
        </div>
        {canManage && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" onClick={handleMarkComplete}
              disabled={!summary || summary.total === 0 || summary.kt_phase_completed}>
              {summary?.kt_phase_completed ? 'KT Complete ✓' : 'Mark KT Complete'}
            </button>
            <button className="btn btn-primary" onClick={openCreate}>+ New KT Task</button>
          </div>
        )}
      </div>

      {actionMsg && <div className="alert" style={{ marginBottom: 16, background: '#ecfdf5', color: '#047857' }}>{actionMsg}</div>}
      {actionError && <div className="error-message" style={{ marginBottom: 16 }}>{actionError}</div>}

      {/* Progress */}
      {summary && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>KT Progress</h3>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{summary.completed}/{summary.total} completed ({completedPct}%)</span>
          </div>
          <div className="kt-progress"><div className="kt-progress-fill" style={{ width: `${completedPct}%` }} /></div>
          <div className="kt-stat-grid" style={{ marginTop: 16 }}>
            <div className="kt-stat"><div className="num">{summary.total}</div><div className="lbl">Total</div></div>
            <div className="kt-stat"><div className="num">{summary.completed}</div><div className="lbl">Completed</div></div>
            <div className="kt-stat"><div className="num">{summary.in_progress}</div><div className="lbl">In Progress</div></div>
            <div className="kt-stat"><div className="num">{summary.pending}</div><div className="lbl">Pending</div></div>
            <div className="kt-stat"><div className="num">{summary.submitted + summary.receiver_review + summary.manager_review}</div><div className="lbl">In Review</div></div>
            <div className="kt-stat"><div className="num">{summary.rejected}</div><div className="lbl">Rejected</div></div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Search</label>
          <input className="form-input" placeholder="Title / responsibility…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Status</label>
          <select className="form-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="PENDING">Pending</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="MANAGER_REVIEW">Manager Review</option>
            <option value="COMPLETED">Completed</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Priority</label>
          <select className="form-input" value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)}>
            <option value="">All</option>
            {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {items.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="clipboard" size={40} /></div>
            <h3>No knowledge transfer tasks</h3>
            <p style={{ color: 'var(--text-secondary)' }}>{canManage ? 'Create a KT task to begin the handover.' : 'No tasks have been assigned yet.'}</p>
          </div>
        ) : (
          <table className="kt-table">
            <thead>
              <tr>
                <th>Project</th><th>Task</th><th>Receiver</th><th>Priority</th><th>Target Date</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map(kt => (
                <tr key={kt.id}>
                  <td>{kt.project_name || '—'}</td>
                  <td>{kt.title}</td>
                  <td>{kt.receiver_name}</td>
                  <td><span className={`badge ${KT_PRIORITY_BADGE[kt.priority]}`}>{kt.priority_display}</span></td>
                  <td>{formatDate(kt.target_completion_date)}</td>
                  <td><span className={`badge ${KT_STATUS_BADGE[kt.status]}`}>{kt.status_display}</span></td>
                  <td><button className="btn btn-ghost" onClick={() => setDetailId(kt.id)}>View</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => !creating && setShowCreate(false)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header"><h3>New Knowledge Transfer Task</h3></div>
            <div className="modal-body" style={{ maxHeight: '65vh', overflowY: 'auto' }}>
              {actionError && <div className="error-message" style={{ marginBottom: 12 }}>{actionError}</div>}
              <div className="form-group">
                <label className="form-label">Title <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input className="form-input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea className="form-input" rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Project</label>
                  <select className="form-input" value={form.project ?? ''} onChange={e => setForm(f => ({ ...f, project: e.target.value ? Number(e.target.value) : null }))}>
                    <option value="">— None —</option>
                    {projects.map(p => <option key={p.id} value={p.id}>{p.name} ({p.code})</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Priority</label>
                  <select className="form-input" value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value as KTPriority }))}>
                    {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Responsibility</label>
                <textarea className="form-input" rows={2} value={form.responsibility} onChange={e => setForm(f => ({ ...f, responsibility: e.target.value }))}
                  placeholder="e.g. Manage production deployments and backend API maintenance." />
              </div>
              <div className="form-group">
                <label className="form-label">Receiver <span style={{ color: 'var(--danger)' }}>*</span></label>
                <select className="form-input" value={form.receiver || ''} onChange={e => setForm(f => ({ ...f, receiver: Number(e.target.value) }))}>
                  <option value="">Select an active employee…</option>
                  {employees.map(e => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} ({e.employee_id})</option>)}
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Start Date</label>
                  <input type="date" className="form-input" value={form.start_date ?? ''} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Target Completion Date</label>
                  <input type="date" className="form-input" value={form.target_completion_date ?? ''} onChange={e => setForm(f => ({ ...f, target_completion_date: e.target.value }))} />
                </div>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Dates are optional and never auto-filled. Enter them manually.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)} disabled={creating}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={creating || !form.title.trim() || !form.receiver}>
                {creating ? <><span className="btn-spinner" /> Creating…</> : 'Create Task'}
              </button>
            </div>
          </div>
        </div>
      )}

      {detailId && (
        <KTDetailModal ktId={detailId} onClose={() => setDetailId(null)} onChanged={loadList} />
      )}
    </div>
  );
}
