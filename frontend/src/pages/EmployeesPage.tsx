import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeService } from '../services/employeeService';
import { useAuthContext } from '../contexts/AuthContext';
import { storage } from '../utils/storage';
import { apiBaseUrl } from '../services/api';
import Icon from '../components/Icon';
import type { EmployeeListItem, EmploymentStatus, EmploymentType, Department } from '../types';

function StatusBadge({ status }: { status: EmploymentStatus }) {
  const map = { ACTIVE: 'badge-active', OFFBOARDING: 'badge-offboarding', EXITED: 'badge-exited' };
  const label = { ACTIVE: 'Active', OFFBOARDING: 'Offboarding', EXITED: 'Exited' };
  return <span className={`badge ${map[status] || ''}`}>{label[status] || status}</span>;
}

function TypeBadge({ type }: { type: EmploymentType }) {
  const map = { FULL_TIME: 'badge-active', PART_TIME: 'badge-employee', CONTRACT: 'badge-manager', INTERN: 'badge-it' };
  const label = { FULL_TIME: 'Full Time', PART_TIME: 'Part Time', CONTRACT: 'Contract', INTERN: 'Intern' };
  return <span className={`badge ${map[type] || ''}`}>{label[type] || type}</span>;
}

function formatDate(d: string) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return d; }
}

export default function EmployeesPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [ordering, setOrdering] = useState('employee_id');
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);

  const canManage = user && (user.role === 'HR' || user.role === 'ADMIN');

  useEffect(() => {
    employeeService.getDepartments({ is_active: true }).then(r => setDepartments(r.results)).catch(() => {});
  }, []);

  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await employeeService.getEmployees({
        page,
        search: search || undefined,
        department: deptFilter || undefined,
        employment_type: typeFilter || undefined,
        status: statusFilter || undefined,
        ordering,
      });
      setEmployees(data.results);
      setTotal(data.count);
      setHasNext(!!data.next);
      setHasPrev(!!data.previous);
    } catch {
      setError('Failed to load employees. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [page, search, deptFilter, typeFilter, statusFilter, ordering]);

  useEffect(() => { fetchEmployees(); }, [fetchEmployees]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  };

  const resetFilters = () => {
    setSearchInput(''); setSearch(''); setDeptFilter('');
    setTypeFilter(''); setStatusFilter(''); setOrdering('employee_id'); setPage(1);
  };

  const hasFilters = search || deptFilter || typeFilter || statusFilter;

  const [exporting, setExporting] = useState(false);
  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (deptFilter) params.set('department', String(deptFilter));
      if (typeFilter) params.set('employment_type', typeFilter);
      if (statusFilter) params.set('status', statusFilter);
      const token = storage.getAccessToken();
      const resp = await fetch(`${apiBaseUrl}/employees/export/?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setError('Export failed.'); return; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `employees_${statusFilter ? statusFilter.toLowerCase() : 'all'}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Export failed.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Employees <span className="count-badge">{total}</span></h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
            {exporting ? <><span className="btn-spinner" /> Exporting…</> : <><Icon name="file" size={15} /> Export CSV</>}
          </button>
          {canManage && (
            <button className="btn btn-primary" onClick={() => navigate('/employees/create')}>
              + Add Employee
            </button>
          )}
        </div>
      </div>

      <div className="filters-bar">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text" className="search-input" placeholder="Search name, email, ID, phone..."
            value={searchInput} onChange={e => setSearchInput(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary">Search</button>
        </form>
        <div className="filter-group">
          <select className="filter-select" value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setPage(1); }}>
            <option value="">All Departments</option>
            {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select className="filter-select" value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1); }}>
            <option value="">All Types</option>
            <option value="FULL_TIME">Full Time</option>
            <option value="PART_TIME">Part Time</option>
            <option value="CONTRACT">Contract</option>
            <option value="INTERN">Intern</option>
          </select>
          <select className="filter-select" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="OFFBOARDING">Offboarding</option>
            <option value="EXITED">Exited</option>
          </select>
          <select className="filter-select" value={ordering} onChange={e => { setOrdering(e.target.value); setPage(1); }}>
            <option value="employee_id">Sort: ID (Asc)</option>
            <option value="-employee_id">Sort: ID (Desc)</option>
            <option value="first_name">Sort: Name (A-Z)</option>
            <option value="-first_name">Sort: Name (Z-A)</option>
            <option value="joining_date">Sort: Joined (Oldest)</option>
            <option value="-joining_date">Sort: Joined (Newest)</option>
          </select>
          {hasFilters && <button type="button" className="btn btn-secondary" onClick={resetFilters}>Clear</button>}
        </div>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Loading employees...</p></div>
        ) : employees.length === 0 ? (
          <div className="empty-state">
            <p>No employees found</p>
            <span>{hasFilters ? 'Try adjusting your search or filters.' : 'No employees added yet.'}</span>
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Employee ID</th>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Designation</th>
                    <th>Manager</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Joining Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map(emp => (
                    <tr key={emp.id}>
                      <td><code style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{emp.employee_id}</code></td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{emp.first_name} {emp.last_name}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{emp.email}</div>
                      </td>
                      <td>{emp.department?.name || '—'}</td>
                      <td>{emp.designation_name || '—'}</td>
                      <td>{emp.manager_name || '—'}</td>
                      <td><TypeBadge type={emp.employment_type} /></td>
                      <td><StatusBadge status={emp.employment_status} /></td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatDate(emp.joining_date)}</td>
                      <td>
                        <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/employees/${emp.id}`)}>
                          View
                        </button>
                        {canManage && (
                          <button className="btn btn-secondary btn-sm" style={{ marginLeft: 6 }} onClick={() => navigate(`/employees/${emp.id}/edit`)}>
                            Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span className="table-count">Showing {employees.length} of {total} employees</span>
              <div className="pagination">
                <button className="btn btn-secondary" disabled={!hasPrev} onClick={() => setPage(p => p - 1)}>Previous</button>
                <span className="page-indicator">Page {page}</span>
                <button className="btn btn-secondary" disabled={!hasNext} onClick={() => setPage(p => p + 1)}>Next</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
