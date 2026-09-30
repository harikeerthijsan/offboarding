import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { offboardingService } from '../services/offboardingService';
import type { ResignationListItem, ResignationStatus } from '../types';
import Icon from '../components/Icon';

const STATUS_LABEL: Record<ResignationStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  MANAGER_REVIEW: 'Manager Review',
  HR_REVIEW: 'HR Review',
  APPROVED: 'Approved',
  NOTICE_PERIOD: 'Notice Period',
  COMPLETED: 'Completed',
  REJECTED: 'Rejected',
  CANCELLED: 'Cancelled',
};

const STATUS_CLASS: Record<ResignationStatus, string> = {
  DRAFT: 'badge-secondary',
  SUBMITTED: 'badge-manager',
  MANAGER_REVIEW: 'badge-it',
  HR_REVIEW: 'badge-employee',
  APPROVED: 'badge-active',
  NOTICE_PERIOD: 'badge-it',
  COMPLETED: 'badge-active',
  REJECTED: 'badge-exited',
  CANCELLED: 'badge-offboarding',
};

function formatDate(d: string | null) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return d; }
}

export default function OffboardingPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [resignations, setResignations] = useState<ResignationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isReviewer = user?.role === 'MANAGER' || user?.role === 'HR' || user?.role === 'ADMIN';
  const isEmployee = user?.role === 'EMPLOYEE' || user?.role === 'MANAGER';

  useEffect(() => {
    offboardingService.listResignations()
      .then(setResignations)
      .catch(() => setError('Failed to load resignation requests.'))
      .finally(() => setLoading(false));
  }, []);

  // Only disable "Submit" if the current user's own employee record has an active resignation
  const hasActive = resignations.some(r =>
    r.employee_user_id === user?.id &&
    ['DRAFT', 'SUBMITTED', 'MANAGER_REVIEW', 'HR_REVIEW'].includes(r.status),
  );

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Offboarding</h1>
          <p className="page-subtitle">Manage resignation requests and offboarding workflow</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {isReviewer && (
            <button className="btn btn-secondary" onClick={() => navigate('/offboarding/requests')}>
              Review Queue
            </button>
          )}
          {isEmployee && (
            <button
              className="btn btn-primary"
              onClick={() => navigate('/offboarding/create')}
              disabled={hasActive}
              title={hasActive ? 'You already have an active resignation request' : ''}
            >
              + Submit Resignation
            </button>
          )}
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {resignations.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon"><Icon name="clipboard" size={40} /></div>
            <h3>No Resignation Requests</h3>
            <p>
              {user?.role === 'EMPLOYEE'
                ? 'You have not submitted any resignation requests yet.'
                : 'No resignation requests found.'}
            </p>
            {isEmployee && (
              <button className="btn btn-primary" onClick={() => navigate('/offboarding/create')}>
                Submit Resignation
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                {user?.role !== 'EMPLOYEE' && <th>Employee</th>}
                {user?.role !== 'EMPLOYEE' && <th>Department</th>}
                <th>Status</th>
                <th>Reason</th>
                <th>Resignation Date</th>
                <th>Submitted</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {resignations.map(r => (
                <tr key={r.id}>
                  {user?.role !== 'EMPLOYEE' && (
                    <td>
                      <strong>{r.employee_name}</strong>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.employee_id}</div>
                    </td>
                  )}
                  {user?.role !== 'EMPLOYEE' && <td>{r.department_name || '—'}</td>}
                  <td>
                    <span className={`badge ${STATUS_CLASS[r.status]}`}>
                      {STATUS_LABEL[r.status]}
                    </span>
                  </td>
                  <td>{r.reason_display}</td>
                  <td>{formatDate(r.resignation_date)}</td>
                  <td>{formatDate(r.created_at)}</td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => navigate(`/offboarding/${r.id}`)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
