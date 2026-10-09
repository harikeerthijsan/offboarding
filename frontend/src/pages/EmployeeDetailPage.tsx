import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { employeeService } from '../services/employeeService';
import { useAuthContext } from '../contexts/AuthContext';
import type { Employee, EmployeeListItem, EmploymentStatus, EmploymentType } from '../types';

function StatusBadge({ status }: { status: EmploymentStatus }) {
  const map: Record<EmploymentStatus, string> = { ACTIVE: 'badge-active', OFFBOARDING: 'badge-offboarding', EXITED: 'badge-exited' };
  return <span className={`badge ${map[status] || ''}`}>{status}</span>;
}
function TypeBadge({ type }: { type: EmploymentType }) {
  const map: Record<EmploymentType, string> = { FULL_TIME: 'badge-active', PART_TIME: 'badge-employee', CONTRACT: 'badge-manager', INTERN: 'badge-it' };
  const labels: Record<EmploymentType, string> = { FULL_TIME: 'Full Time', PART_TIME: 'Part Time', CONTRACT: 'Contract', INTERN: 'Intern' };
  return <span className={`badge ${map[type] || ''}`}>{labels[type] || type}</span>;
}
function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }); }
  catch { return d; }
}
function InfoRow({ label, value }: { label: string; value?: string | React.ReactNode | null }) {
  return (
    <div className="info-row">
      <dt className="info-label">{label}</dt>
      <dd className="info-value">{value || '—'}</dd>
    </div>
  );
}

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthContext();
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [reports, setReports] = useState<EmployeeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const canManage = user && (user.role === 'HR' || user.role === 'ADMIN');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    employeeService.getEmployee(Number(id))
      .then(emp => {
        setEmployee(emp);
        if (emp.direct_reports_count > 0) {
          return employeeService.getReports(emp.id).then(setReports);
        }
      })
      .catch((err: { response?: { status?: number } }) => {
        if (err.response?.status === 404) setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="loading-state" style={{ minHeight: 300 }}><div className="spinner" /></div>;
  if (notFound || !employee) return (
    <div className="empty-state" style={{ minHeight: 300 }}>
      <p>Employee not found</p>
      <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={() => navigate('/employees')}>Back to Employees</button>
    </div>
  );

  const fullName = `${employee.first_name} ${employee.last_name}`;
  const initials = `${employee.first_name[0]}${employee.last_name[0]}`.toUpperCase();
  // For exited employees, show only core employee information (Personal + Employment).
  const isExited = employee.employment_status === 'EXITED';

  return (
    <div className="employee-detail">
      <div className="detail-toolbar">
        <button className="btn btn-secondary" onClick={() => navigate('/employees')}>← Back</button>
        {canManage && (
          <button className="btn btn-primary" onClick={() => navigate(`/employees/${employee.id}/edit`)}>Edit Employee</button>
        )}
      </div>

      {/* Overview Card */}
      <div className="card detail-overview">
        <div className="overview-avatar">{initials}</div>
        <div className="overview-info">
          <h2 className="overview-name">{fullName}</h2>
          <p className="overview-sub">{employee.designation?.name || 'No designation'}</p>
          <p className="overview-sub" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{employee.employee_id}</p>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <StatusBadge status={employee.employment_status} />
            <TypeBadge type={employee.employment_type} />
          </div>
        </div>
      </div>

      <div className="detail-grid">
        {/* Employment Info */}
        <div className="card">
          <h3 className="section-title">Employment Information</h3>
          <dl className="info-list">
            <InfoRow label="Department" value={employee.department?.name} />
            <InfoRow label="Designation" value={employee.designation?.name} />
            <InfoRow label="Employment Type" value={employee.employment_type.replace('_', ' ')} />
            <InfoRow label="Employment Status" value={<StatusBadge status={employee.employment_status} />} />
            <InfoRow label="Joining Date" value={formatDate(employee.joining_date)} />
            <InfoRow label="Location" value={employee.location} />
            <InfoRow label="Manager" value={employee.manager ? `${employee.manager.first_name} ${employee.manager.last_name} (${employee.manager.email})` : '—'} />
          </dl>
        </div>

        {/* Personal Info */}
        <div className="card">
          <h3 className="section-title">Personal Information</h3>
          <dl className="info-list">
            <InfoRow label="Email" value={employee.email} />
            <InfoRow label="Phone" value={employee.phone} />
            <InfoRow label="Date of Birth" value={formatDate(employee.date_of_birth)} />
            <InfoRow label="Gender" value={employee.gender ? employee.gender.replace('_', ' ') : '—'} />
            <InfoRow label="Address" value={employee.address} />
          </dl>
        </div>

        {/* Emergency Contact */}
        {!isExited && (
          <div className="card">
            <h3 className="section-title">Emergency Contact</h3>
            <dl className="info-list">
              <InfoRow label="Contact Name" value={employee.emergency_contact_name} />
              <InfoRow label="Contact Phone" value={employee.emergency_contact_phone} />
            </dl>
          </div>
        )}

        {/* Statutory Details — HR/Admin only */}
        {!isExited && canManage && (
          <div className="card">
            <h3 className="section-title">Statutory Details</h3>
            <dl className="info-list">
              <InfoRow label="Aadhaar Number" value={employee.aadhaar_number} />
              <InfoRow label="PAN Number" value={employee.pan_number} />
              <InfoRow label="UAN (PF)" value={employee.uan_number} />
              <InfoRow label="ESI Number" value={employee.esi_number} />
            </dl>
          </div>
        )}

        {/* Bank Details — HR/Admin only */}
        {!isExited && canManage && (
          <div className="card">
            <h3 className="section-title">Bank Details</h3>
            <dl className="info-list">
              <InfoRow label="Bank Name" value={employee.bank_name} />
              <InfoRow label="Account Holder" value={employee.bank_account_holder_name} />
              <InfoRow label="Account Number" value={employee.bank_account_number} />
              <InfoRow label="IFSC Code" value={employee.bank_ifsc_code} />
            </dl>
          </div>
        )}

        {/* System Info */}
        {!isExited && (
          <div className="card">
            <h3 className="section-title">System Information</h3>
            <dl className="info-list">
              <InfoRow label="User Role" value={employee.user?.role} />
              <InfoRow label="User Email" value={employee.user?.email} />
              <InfoRow label="Direct Reports" value={String(employee.direct_reports_count)} />
              <InfoRow label="Record Created" value={formatDate(employee.created_at)} />
              <InfoRow label="Last Updated" value={formatDate(employee.updated_at)} />
            </dl>
          </div>
        )}
      </div>

      {/* Direct Reports */}
      {!isExited && reports.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 className="section-title">Direct Reports ({reports.length})</h3>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Employee ID</th><th>Name</th><th>Designation</th><th>Status</th><th></th>
                </tr>
              </thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id}>
                    <td><code style={{ fontSize: 12 }}>{r.employee_id}</code></td>
                    <td>{r.first_name} {r.last_name}</td>
                    <td>{r.designation_name || '—'}</td>
                    <td><span className={`badge badge-${r.employment_status.toLowerCase()}`}>{r.employment_status}</span></td>
                    <td><button className="btn btn-secondary btn-sm" onClick={() => navigate(`/employees/${r.id}`)}>View</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
