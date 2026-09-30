import { useEffect, useState, useCallback, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { hrOffboardingService, type OffboardingListFilters } from '../services/hrOffboardingService';
import { employeeService } from '../services/employeeService';
import type { HRDashboardData, HROffboardingRow, Department, PaginatedResponse } from '../types';
import { FINAL_REVIEW_BADGE, FINAL_REVIEW_LABEL } from '../utils/finalReview';
import { formatDate } from '../utils/kt';
import Icon from '../components/Icon';

const SUMMARY_CARDS: { key: keyof HRDashboardData['summary']; label: string; accent?: boolean }[] = [
  { key: 'total_offboarding', label: 'Total Offboarding', accent: true },
  { key: 'pending_manager_review', label: 'Pending Manager Review' },
  { key: 'pending_hr_review', label: 'Pending HR Review' },
  { key: 'notice_period', label: 'Notice Period' },
  { key: 'kt_in_progress', label: 'KT In Progress' },
  { key: 'clearance_pending', label: 'Clearance Pending' },
  { key: 'settlement_pending', label: 'Settlement Pending' },
  { key: 'exit_interview_pending', label: 'Exit Interview Pending' },
  { key: 'ready_for_final_review', label: 'Ready for Final Review', accent: true },
  { key: 'under_final_review', label: 'Under Final Review' },
  { key: 'completed', label: 'Completed', accent: true },
];

const PIPELINE_STAGES: { key: keyof HRDashboardData['pipeline']; label: string }[] = [
  { key: 'resignation', label: 'Resignation' },
  { key: 'notice', label: 'Notice' },
  { key: 'kt', label: 'KT' },
  { key: 'clearance', label: 'Clearance' },
  { key: 'settlement', label: 'Settlement' },
  { key: 'exit_interview', label: 'Exit Interview' },
  { key: 'final_review', label: 'Final Review' },
  { key: 'completed', label: 'Completed' },
];

export default function HRDashboardPage() {
  const navigate = useNavigate();
  const [dash, setDash] = useState<HRDashboardData | null>(null);
  const [rows, setRows] = useState<PaginatedResponse<HROffboardingRow> | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState<OffboardingListFilters>({ page: 1 });

  const loadList = useCallback(async () => {
    const data = await hrOffboardingService.list(filters);
    setRows(data);
  }, [filters]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [d] = await Promise.all([hrOffboardingService.dashboard()]);
        setDash(d);
        await loadList();
        try { const deps = await employeeService.getDepartments({ is_active: true }); setDepartments(deps.results); } catch { /* ignore */ }
      } catch {
        setError('Failed to load the HR dashboard.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line
  }, []);

  useEffect(() => { if (!loading) loadList().catch(() => {}); /* eslint-disable-next-line */ }, [filters]);

  function setFilter(k: keyof OffboardingListFilters, v: string) {
    setFilters(f => ({ ...f, [k]: v || undefined, page: 1 }));
  }

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>;
  if (error) return <div className="error-message">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">HR Offboarding Dashboard</h1>
          <p className="page-subtitle">Company-wide offboarding pipeline and final approvals.</p>
        </div>
      </div>

      {/* Summary cards */}
      {dash && (
        <div className="dash-grid">
          {SUMMARY_CARDS.map(c => (
            <div key={c.key} className={`dash-card${c.accent ? ' accent' : ''}`}>
              <div className="num">{dash.summary[c.key]}</div>
              <div className="lbl">{c.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Pipeline */}
      {dash && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Offboarding Pipeline</h3>
          <div className="pipeline">
            {PIPELINE_STAGES.map((s, i) => (
              <Fragment key={s.key}>
                <div className="pipeline-stage">
                  <div className="pnum">{dash.pipeline[s.key]}</div>
                  <div className="plbl">{s.label}</div>
                </div>
                {i < PIPELINE_STAGES.length - 1 && <div className="pipeline-arrow">→</div>}
              </Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div className="form-group" style={{ marginBottom: 0, flex: 1, minWidth: 180 }}>
          <label className="form-label">Search</label>
          <input className="form-input" placeholder="Name / ID / email…" value={filters.search ?? ''} onChange={e => setFilter('search', e.target.value)} />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Department</label>
          <select className="form-input" value={filters.department ?? ''} onChange={e => setFilter('department', e.target.value)}>
            <option value="">All</option>
            {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Final Review</label>
          <select className="form-input" value={filters.final_review_status ?? ''} onChange={e => setFilter('final_review_status', e.target.value)}>
            <option value="">All</option>
            <option value="NOT_READY">Not Ready</option>
            <option value="UNDER_REVIEW">Under Review</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Settlement</label>
          <select className="form-input" value={filters.settlement_status ?? ''} onChange={e => setFilter('settlement_status', e.target.value)}>
            <option value="">All</option>
            <option value="DRAFT">Draft</option>
            <option value="UNDER_REVIEW">Under Review</option>
            <option value="APPROVED">Approved</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {!rows || rows.results.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="bar-chart" size={40} /></div><h3>No offboarding records</h3>
            <p style={{ color: 'var(--text-secondary)' }}>No records match your filters.</p>
          </div>
        ) : (
          <>
            <table className="kt-table">
              <thead>
                <tr>
                  <th>Employee</th><th>ID</th><th>Department</th><th>Manager</th>
                  <th>Stage</th><th>Resignation</th><th>Expected LWD</th>
                  <th>KT</th><th>Clearance</th><th>Settlement</th><th>Exit</th><th>Final</th><th></th>
                </tr>
              </thead>
              <tbody>
                {rows.results.map(r => (
                  <tr key={r.id}>
                    <td>{r.employee_name}</td>
                    <td>{r.employee_id}</td>
                    <td>{r.department_name || '—'}</td>
                    <td>{r.manager_name || '—'}</td>
                    <td>{r.current_stage}</td>
                    <td>{formatDate(r.resignation_date)}</td>
                    <td>{r.expected_last_working_day ? formatDate(r.expected_last_working_day) : 'Not entered'}</td>
                    <td>{r.kt_status}</td>
                    <td>{r.clearance_status}</td>
                    <td>{r.settlement_status}</td>
                    <td>{r.exit_interview_status}</td>
                    <td><span className={`badge ${FINAL_REVIEW_BADGE[r.final_review_status]}`}>{FINAL_REVIEW_LABEL[r.final_review_status]}</span></td>
                    <td><button className="btn btn-ghost" onClick={() => navigate(`/offboarding/${r.id}/final-review`)}>Review</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="table-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
              <span className="table-count">{rows.count} record(s)</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" disabled={!rows.previous}
                  onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) - 1 }))}>Previous</button>
                <button className="btn btn-secondary" disabled={!rows.next}
                  onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) + 1 }))}>Next</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
