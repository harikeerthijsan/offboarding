import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeService } from '../services/employeeService';
import { useAuthContext } from '../contexts/AuthContext';
import type { Department, Designation, EmployeeListItem } from '../types';

type Tab = 'departments' | 'designations' | 'hierarchy';

function DepartmentForm({ onSave, onCancel, initial }: {
  onSave: (data: Partial<Department>) => Promise<void>;
  onCancel: () => void;
  initial?: Partial<Department>;
}) {
  const [form, setForm] = useState({ name: initial?.name || '', code: initial?.code || '', description: initial?.description || '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (f: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm(p => ({ ...p, [f]: e.target.value }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required'); return; }
    setLoading(true);
    try { await onSave(form); } catch { setError('Failed to save. Please try again.'); } finally { setLoading(false); }
  };
  return (
    <form onSubmit={submit} className="inline-form">
      {error && <div className="error-message" style={{ marginBottom: 8 }}>{error}</div>}
      <div className="form-grid-3">
        <div className="form-group"><label className="form-label">Name *</label><input className="form-input" value={form.name} onChange={set('name')} /></div>
        <div className="form-group"><label className="form-label">Code</label><input className="form-input" value={form.code} onChange={set('code')} placeholder="ENG" /></div>
        <div className="form-group"><label className="form-label">Description</label><input className="form-input" value={form.description} onChange={set('description')} /></div>
      </div>
      <div className="form-actions" style={{ marginTop: 8 }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? 'Saving...' : 'Save'}</button>
      </div>
    </form>
  );
}

function DesignationForm({ departments, onSave, onCancel }: {
  departments: Department[];
  onSave: (data: Partial<Designation>) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({ name: '', code: '', department: '', description: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (f: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm(p => ({ ...p, [f]: e.target.value }));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required'); return; }
    setLoading(true);
    try { await onSave({ ...form, department: form.department ? Number(form.department) as unknown as number : undefined }); }
    catch { setError('Failed to save.'); } finally { setLoading(false); }
  };
  return (
    <form onSubmit={submit} className="inline-form">
      {error && <div className="error-message" style={{ marginBottom: 8 }}>{error}</div>}
      <div className="form-grid-3">
        <div className="form-group"><label className="form-label">Name *</label><input className="form-input" value={form.name} onChange={set('name')} /></div>
        <div className="form-group"><label className="form-label">Code</label><input className="form-input" value={form.code} onChange={set('code')} /></div>
        <div className="form-group"><label className="form-label">Department</label>
          <select className="form-input" value={form.department} onChange={set('department')}>
            <option value="">No department</option>
            {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
      </div>
      <div className="form-actions" style={{ marginTop: 8 }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? 'Saving...' : 'Save'}</button>
      </div>
    </form>
  );
}

type EmployeeNode = EmployeeListItem & { children: EmployeeNode[] };

function HierarchyNode({ employee, level, navigate }: { employee: EmployeeNode; level: number; navigate: (path: string) => void }) {
  const [expanded, setExpanded] = useState(level < 2);
  const hasChildren = employee.children && employee.children.length > 0;
  return (
    <div className="hierarchy-node" style={{ marginLeft: level * 24 }}>
      <div className="hierarchy-item">
        <button className="hierarchy-toggle" onClick={() => setExpanded(e => !e)} disabled={!hasChildren}>
          {hasChildren ? (expanded ? '▼' : '▶') : '•'}
        </button>
        <div className="hierarchy-card" onClick={() => navigate(`/employees/${employee.id}`)}>
          <span className="hierarchy-name">{employee.first_name} {employee.last_name}</span>
          <span className="hierarchy-detail">{employee.designation_name || employee.department?.name || ''}</span>
          <span className={`badge badge-${employee.employment_status.toLowerCase()}`} style={{ fontSize: 11 }}>{employee.employment_status}</span>
        </div>
      </div>
      {expanded && hasChildren && (
        <div className="hierarchy-children">
          {employee.children.map(child => <HierarchyNode key={child.id} employee={child} level={level + 1} navigate={navigate} />)}
        </div>
      )}
    </div>
  );
}

export default function OrganizationPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('departments');
  const canManage = user && (user.role === 'HR' || user.role === 'ADMIN');

  const [departments, setDepartments] = useState<Department[]>([]);
  const [deptLoading, setDeptLoading] = useState(true);
  const [showDeptForm, setShowDeptForm] = useState(false);

  const [designations, setDesignations] = useState<Designation[]>([]);
  const [desigLoading, setDesigLoading] = useState(false);
  const [showDesigForm, setShowDesigForm] = useState(false);
  const [desigDeptFilter, setDesigDeptFilter] = useState('');

  const [hierarchyRoots, setHierarchyRoots] = useState<EmployeeNode[]>([]);
  const [hierarchyLoading, setHierarchyLoading] = useState(false);

  const loadDepartments = useCallback(() => {
    setDeptLoading(true);
    employeeService.getDepartments().then(r => setDepartments(r.results)).catch(() => {}).finally(() => setDeptLoading(false));
  }, []);

  const loadDesignations = useCallback(() => {
    setDesigLoading(true);
    const params: { department?: number } = {};
    if (desigDeptFilter) params.department = Number(desigDeptFilter);
    employeeService.getDesignations(params).then(r => setDesignations(r.results)).catch(() => {}).finally(() => setDesigLoading(false));
  }, [desigDeptFilter]);

  const loadHierarchy = useCallback(async () => {
    setHierarchyLoading(true);
    try {
      const allEmps: import('../types').EmployeeListItem[] = [];
      let page = 1;
      while (true) {
        const data = await employeeService.getEmployees({ status: 'ACTIVE', page, page_size: 100 });
        allEmps.push(...data.results);
        if (!data.next) break;
        page++;
      }
      const emps = allEmps;
      const byId = new Map<number, EmployeeNode>(emps.map(e => [e.id, { ...e, children: [] }]));
      const roots: EmployeeNode[] = [];
      emps.forEach(e => {
        if (e.manager_id && byId.has(e.manager_id)) {
          byId.get(e.manager_id)!.children.push(byId.get(e.id)!);
        } else {
          const node = byId.get(e.id);
          if (node) roots.push(node);
        }
      });
      setHierarchyRoots(roots);
    } catch { setHierarchyRoots([]); } finally { setHierarchyLoading(false); }
  }, []);

  useEffect(() => { loadDepartments(); }, [loadDepartments]);
  useEffect(() => { if (tab === 'designations') loadDesignations(); }, [tab, loadDesignations]);
  useEffect(() => { if (tab === 'hierarchy') loadHierarchy(); }, [tab, loadHierarchy]);

  const handleSaveDept = async (data: Partial<Department>) => {
    await employeeService.createDepartment(data);
    setShowDeptForm(false);
    loadDepartments();
  };

  const handleSaveDesig = async (data: Partial<Designation>) => {
    await employeeService.createDesignation(data);
    setShowDesigForm(false);
    loadDesignations();
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Organization</h1>
      </div>

      <div className="tab-bar">
        {(['departments', 'designations', 'hierarchy'] as Tab[]).map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'departments' && (
        <div>
          {canManage && !showDeptForm && (
            <div style={{ marginBottom: 12 }}>
              <button className="btn btn-primary" onClick={() => setShowDeptForm(true)}>+ Add Department</button>
            </div>
          )}
          {showDeptForm && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 className="section-title" style={{ marginBottom: 12 }}>New Department</h3>
              <DepartmentForm onSave={handleSaveDept} onCancel={() => setShowDeptForm(false)} />
            </div>
          )}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {deptLoading ? <div className="loading-state"><div className="spinner" /></div> : (
              departments.length === 0 ? <div className="empty-state"><p>No departments</p></div> : (
                <table>
                  <thead><tr><th>Name</th><th>Code</th><th>Head</th><th>Active Employees</th><th>Status</th></tr></thead>
                  <tbody>
                    {departments.map(d => (
                      <tr key={d.id}>
                        <td><div style={{ fontWeight: 500 }}>{d.name}</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.description}</div></td>
                        <td><code style={{ fontSize: 12 }}>{d.code || '—'}</code></td>
                        <td>{d.head_name || '—'}</td>
                        <td>{d.employee_count}</td>
                        <td><span className={`badge ${d.is_active ? 'badge-active' : 'badge-exited'}`}>{d.is_active ? 'Active' : 'Inactive'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>
        </div>
      )}

      {tab === 'designations' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <select className="filter-select" value={desigDeptFilter} onChange={e => setDesigDeptFilter(e.target.value)}>
              <option value="">All Departments</option>
              {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            {canManage && !showDesigForm && (
              <button className="btn btn-primary" onClick={() => setShowDesigForm(true)}>+ Add Designation</button>
            )}
          </div>
          {showDesigForm && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 className="section-title" style={{ marginBottom: 12 }}>New Designation</h3>
              <DesignationForm departments={departments} onSave={handleSaveDesig} onCancel={() => setShowDesigForm(false)} />
            </div>
          )}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {desigLoading ? <div className="loading-state"><div className="spinner" /></div> : (
              designations.length === 0 ? (
                <div className="empty-state">
                  <p>No designations</p>
                  <span>{desigDeptFilter ? 'No designations for this department.' : 'No designations created yet.'}</span>
                </div>
              ) : (
                <table>
                  <thead><tr><th>Name</th><th>Code</th><th>Department</th><th>Status</th></tr></thead>
                  <tbody>
                    {designations.map(d => (
                      <tr key={d.id}>
                        <td><div style={{ fontWeight: 500 }}>{d.name}</div></td>
                        <td><code style={{ fontSize: 12 }}>{d.code || '—'}</code></td>
                        <td>{d.department_name || '—'}</td>
                        <td><span className={`badge ${d.is_active ? 'badge-active' : 'badge-exited'}`}>{d.is_active ? 'Active' : 'Inactive'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>
        </div>
      )}

      {tab === 'hierarchy' && (
        <div className="card">
          {hierarchyLoading ? <div className="loading-state"><div className="spinner" /></div> : (
            hierarchyRoots.length === 0 ? <div className="empty-state"><p>No employees found</p></div> : (
              <div className="hierarchy-tree">
                {hierarchyRoots.map(r => <HierarchyNode key={r.id} employee={r} level={0} navigate={navigate} />)}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
