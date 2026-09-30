import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clearanceService, type ClearanceQueueRow } from '../services/clearanceService';
import Icon from '../components/Icon';
import { DEPT_STATUS_BADGE } from '../utils/clearance';
import type { DepartmentClearanceStatus } from '../types';

export default function ClearanceQueuePage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<ClearanceQueueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    clearanceService.queue()
      .then(setRows)
      .catch(() => setError('Failed to load clearances.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Clearances</h1>
          <p className="page-subtitle">Offboardings awaiting your clearance action.</p>
        </div>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card">
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
        ) : rows.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="check" size={40} /></div>
            <h3>Nothing pending</h3>
            <p style={{ color: 'var(--text-secondary)' }}>There are no clearances awaiting your action.</p>
          </div>
        ) : (
          <table className="kt-table">
            <thead>
              <tr>
                <th>Employee</th><th>ID</th><th>Department</th><th>Clearance</th>
                <th>Status</th><th>Assets Pending</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.employee_name}</td>
                  <td>{r.employee_id}</td>
                  <td>{r.employee_department || '—'}</td>
                  <td>{r.department_display}</td>
                  <td><span className={`badge ${DEPT_STATUS_BADGE[r.status as DepartmentClearanceStatus] || ''}`}>{r.status_display}</span></td>
                  <td>{r.department === 'IT' ? r.pending_assets : '—'}</td>
                  <td>
                    <button className="btn btn-primary" onClick={() => navigate(`/offboarding/${r.offboarding_id}/clearance`)}>
                      Open Clearance
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
