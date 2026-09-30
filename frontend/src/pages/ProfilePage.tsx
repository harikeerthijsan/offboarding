import { useEffect, useState } from 'react';
import { authService } from '../services/authService';
import { employeeService } from '../services/employeeService';
import { useAuthContext } from '../contexts/AuthContext';
import type { User, Employee } from '../types';

function getInitials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }); }
  catch { return d; }
}

export default function ProfilePage() {
  const { user: cachedUser } = useAuthContext();
  const [user, setUser] = useState<User | null>(cachedUser);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const userData = await authService.getCurrentUser();
        setUser(userData);
      } catch {
        setError('Failed to load user data. Showing cached data.');
      }
      try {
        const empData = await employeeService.getMyProfile();
        setEmployee(empData);
      } catch {
        // Employee profile may not exist for all users — fail gracefully
      }
      setLoading(false);
    };
    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">My Profile</h1>
        </div>
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">My Profile</h1>
        </div>
        {error && <div className="error-message">{error}</div>}
      </div>
    );
  }

  const displayName = user.first_name
    ? `${user.first_name} ${user.last_name}`.trim()
    : user.username;

  const initials = getInitials(
    user.first_name || user.username,
    user.last_name || ''
  );

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">My Profile</h1>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card profile-card">
        <div className="profile-header">
          <div className="profile-avatar">{initials}</div>
          <div className="profile-info">
            <h2 className="profile-name">{displayName}</h2>
            <p className="profile-email">{user.email}</p>
            <span className={`badge badge-${user.role.toLowerCase()}`}>{user.role}</span>
          </div>
        </div>

        <div className="profile-divider" />

        <div className="profile-details">
          <h3 className="profile-section-title">Account Details</h3>
          <dl className="profile-fields">
            <div className="profile-field">
              <dt>Username</dt>
              <dd>{user.username}</dd>
            </div>
            <div className="profile-field">
              <dt>First Name</dt>
              <dd>{user.first_name || '—'}</dd>
            </div>
            <div className="profile-field">
              <dt>Last Name</dt>
              <dd>{user.last_name || '—'}</dd>
            </div>
            <div className="profile-field">
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div className="profile-field">
              <dt>Role</dt>
              <dd>{user.role}</dd>
            </div>
            <div className="profile-field">
              <dt>Account Status</dt>
              <dd>
                <span className={`badge ${user.is_active ? 'badge-active' : 'badge-exited'}`}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </dd>
            </div>
            <div className="profile-field">
              <dt>User ID</dt>
              <dd>#{user.id}</dd>
            </div>
            {user.date_joined && (
              <div className="profile-field">
                <dt>Joined</dt>
                <dd>{formatDate(user.date_joined)}</dd>
              </div>
            )}
          </dl>
        </div>

        {employee && (
          <>
            <div className="profile-divider" />
            <div className="profile-details">
              <h3 className="profile-section-title">Employee Details</h3>
              <dl className="profile-fields">
                <div className="profile-field">
                  <dt>Employee ID</dt>
                  <dd>{employee.employee_id}</dd>
                </div>
                <div className="profile-field">
                  <dt>Department</dt>
                  <dd>{employee.department?.name || '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Designation</dt>
                  <dd>{employee.designation?.name || '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Employment Type</dt>
                  <dd>{employee.employment_type?.replace('_', ' ') || '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Employment Status</dt>
                  <dd>
                    <span className={`badge badge-${employee.employment_status?.toLowerCase()}`}>
                      {employee.employment_status}
                    </span>
                  </dd>
                </div>
                <div className="profile-field">
                  <dt>Joining Date</dt>
                  <dd>{formatDate(employee.joining_date)}</dd>
                </div>
                <div className="profile-field">
                  <dt>Location</dt>
                  <dd>{employee.location || '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Phone</dt>
                  <dd>{employee.phone || '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Manager</dt>
                  <dd>{employee.manager ? `${employee.manager.first_name} ${employee.manager.last_name}` : '—'}</dd>
                </div>
                <div className="profile-field">
                  <dt>Direct Reports</dt>
                  <dd>{employee.direct_reports_count}</dd>
                </div>
              </dl>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
