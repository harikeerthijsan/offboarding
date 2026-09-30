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

const FILTER_TABS: { label: string; value: string }[] = [
  { label: 'All', value: '' },
  { label: 'Pending Review', value: 'SUBMITTED' },
  { label: 'With HR', value: 'MANAGER_REVIEW' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Notice Period', value: 'NOTICE_PERIOD' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Rejected', value: 'REJECTED' },
];

export default function OffboardingRequestsPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [resignations, setResignations] = useState<ResignationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Only managers, HR, and admins should see this page
  const isAllowed = user?.role === 'MANAGER' || user?.role === 'HR' || user?.role === 'ADMIN';

  useEffect(() => {
    if (!isAllowed) {
      navigate('/offboarding');
      return;
    }
    setLoading(true);
    offboardingService.listResignations(statusFilter || undefined)
      .then(setResignations)
      .catch(() => setError('Failed to load requests.'))
      .finally(() => setLoading(false));
  }, [statusFilter, isAllowed, navigate]);

  const pendingForMe = resignations.filter(r => {
    if (user?.role === 'MANAGER') return r.status === 'SUBMITTED';
    if (user?.role === 'HR' || user?.role === 'ADMIN') return r.status === 'MANAGER_REVIEW';
    return false;
  }).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <button className="btn btn-ghost" onClick={() => navigate('/offboarding')} style={{ marginBottom: 8 }}>
            ← Back
          </button>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-subtitle">
            {user?.role === 'MANAGER'
              ? 'Resignation requests from your direct reports'
              : 'All resignation requests pending review'}
          </p>
        </div>
        {pendingForMe > 0 && (
          <div className="stat-highlight">
            <span className="stat-number">{pendingForMe}</span>
            <span className="stat-label">Pending your action</span>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Filter Tabs */}
      <div className="tab-bar" style={{ marginBottom: 16 }}>
        {FILTER_TABS.map(tab => (
          <button
            key={tab.value}
            className={`tab-btn${statusFilter === tab.value ? ' active' : ''}`}
            onClick={() => setStatusFilter(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : resignations.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon"><Icon name="check" size={40} /></div>
            <h3>No Requests Found</h3>
            <p>
              {statusFilter
                ? `No resignation requests with status "${STATUS_LABEL[statusFilter as ResignationStatus] || statusFilter}".`
                : 'No resignation requests found.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Resignation Date</th>
                <th>Submitted</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {resignations.map(r => {
                const needsMyAction =
                  (user?.role === 'MANAGER' && r.status === 'SUBMITTED') ||
                  ((user?.role === 'HR' || user?.role === 'ADMIN') && r.status === 'MANAGER_REVIEW');
                return (
                  <tr key={r.id} style={needsMyAction ? { background: 'var(--primary-light)' } : {}}>
                    <td>
                      <strong>{r.employee_name}</strong>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.employee_id}</div>
                    </td>
                    <td>{r.department_name || '—'}</td>
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
                        className={`btn btn-sm ${needsMyAction ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => navigate(`/offboarding/${r.id}`)}
                      >
                        {needsMyAction ? 'Review' : 'View'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
