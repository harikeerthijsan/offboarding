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

interface PersonalForm {
  phone: string;
  date_of_birth: string;
  gender: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  aadhaar_number: string;
  pan_number: string;
  uan_number: string;
  esi_number: string;
  bank_name: string;
  bank_account_holder_name: string;
  bank_account_number: string;
  bank_ifsc_code: string;
}

function toForm(emp: Employee): PersonalForm {
  return {
    phone: emp.phone || '',
    date_of_birth: emp.date_of_birth || '',
    gender: emp.gender || '',
    address: emp.address || '',
    emergency_contact_name: emp.emergency_contact_name || '',
    emergency_contact_phone: emp.emergency_contact_phone || '',
    aadhaar_number: emp.aadhaar_number || '',
    pan_number: emp.pan_number || '',
    uan_number: emp.uan_number || '',
    esi_number: emp.esi_number || '',
    bank_name: emp.bank_name || '',
    bank_account_holder_name: emp.bank_account_holder_name || '',
    bank_account_number: emp.bank_account_number || '',
    bank_ifsc_code: emp.bank_ifsc_code || '',
  };
}

function InfoField({ label, value }: { label: string; value?: string | React.ReactNode | null }) {
  return (
    <div className="profile-field">
      <dt>{label}</dt>
      <dd>{value || '—'}</dd>
    </div>
  );
}

export default function ProfilePage() {
  const { user: cachedUser } = useAuthContext();
  const [user, setUser] = useState<User | null>(cachedUser);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<PersonalForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState('');

  // Change-password state
  const [pwOpen, setPwOpen] = useState(false);
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwErrors, setPwErrors] = useState<Record<string, string>>({});
  const [pwSaving, setPwSaving] = useState(false);
  const [pwSuccess, setPwSuccess] = useState('');

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
        setForm(toForm(empData));
      } catch {
        // Employee profile may not exist for all users — fail gracefully
      }
      setLoading(false);
    };
    fetchProfile();
  }, []);

  const set = (field: keyof PersonalForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm(f => (f ? { ...f, [field]: e.target.value } : f));
    setErrors(prev => ({ ...prev, [field]: '' }));
  };

  const startEdit = () => {
    if (employee) setForm(toForm(employee));
    setErrors({});
    setSuccess('');
    setEditing(true);
  };

  const cancelEdit = () => {
    if (employee) setForm(toForm(employee));
    setErrors({});
    setEditing(false);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setErrors({});
    setSuccess('');
    const payload: Record<string, unknown> = {
      phone: form.phone,
      date_of_birth: form.date_of_birth || null,
      gender: form.gender,
      address: form.address,
      emergency_contact_name: form.emergency_contact_name,
      emergency_contact_phone: form.emergency_contact_phone,
      aadhaar_number: form.aadhaar_number.replace(/\s/g, ''),
      pan_number: form.pan_number.toUpperCase().trim(),
      uan_number: form.uan_number.trim(),
      esi_number: form.esi_number.trim(),
      bank_name: form.bank_name,
      bank_account_holder_name: form.bank_account_holder_name,
      bank_account_number: form.bank_account_number.trim(),
      bank_ifsc_code: form.bank_ifsc_code.toUpperCase().trim(),
    };
    try {
      const updated = await employeeService.updateMyProfile(payload);
      setEmployee(updated);
      setForm(toForm(updated));
      setEditing(false);
      setSuccess('Your details were updated successfully.');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: Record<string, string[]> } };
      if (axiosErr.response?.data) {
        const fieldErrors: Record<string, string> = {};
        Object.entries(axiosErr.response.data).forEach(([k, v]) => { fieldErrors[k] = Array.isArray(v) ? v[0] : String(v); });
        setErrors(fieldErrors);
      } else {
        setErrors({ _: 'Could not save. Please try again.' });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwErrors({});
    setPwSuccess('');
    const errs: Record<string, string> = {};
    if (!pwForm.current) errs.current_password = 'Enter your current password';
    if (!pwForm.next) errs.new_password = 'Enter a new password';
    else if (pwForm.next.length < 8) errs.new_password = 'Password must be at least 8 characters';
    if (pwForm.next !== pwForm.confirm) errs.confirm_password = 'Passwords do not match';
    if (Object.keys(errs).length) { setPwErrors(errs); return; }

    setPwSaving(true);
    try {
      await authService.changePassword(pwForm.current, pwForm.next, pwForm.confirm);
      setPwForm({ current: '', next: '', confirm: '' });
      setPwOpen(false);
      setPwSuccess('Your password was changed successfully.');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: Record<string, string[] | string> } };
      if (axiosErr.response?.data) {
        const fieldErrors: Record<string, string> = {};
        Object.entries(axiosErr.response.data).forEach(([k, v]) => {
          const key = k === 'detail' || k === 'non_field_errors' ? '_' : k;
          fieldErrors[key] = Array.isArray(v) ? v[0] : String(v);
        });
        setPwErrors(fieldErrors);
      } else {
        setPwErrors({ _: 'Could not change password. Please try again.' });
      }
    } finally {
      setPwSaving(false);
    }
  };

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

  const initials = getInitials(user.first_name || user.username, user.last_name || '');

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">My Profile</h1>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}
      {success && <div className="success-message" style={{ marginBottom: 16 }}>{success}</div>}
      {errors._ && <div className="error-message" style={{ marginBottom: 16 }}>{errors._}</div>}

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

        {/* Account & employment details — read-only (managed by HR) */}
        <div className="profile-details">
          <h3 className="profile-section-title">Account & Employment</h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: -6, marginBottom: 12 }}>
            These details are managed by HR. Contact HR if anything is incorrect.
          </p>
          <dl className="profile-fields">
            <InfoField label="Username" value={user.username} />
            <InfoField label="Email" value={user.email} />
            <InfoField label="Role" value={user.role} />
            {employee && <InfoField label="Employee ID" value={employee.employee_id} />}
            {employee && <InfoField label="Department" value={employee.department?.name} />}
            {employee && <InfoField label="Designation" value={employee.designation?.name} />}
            {employee && <InfoField label="Employment Type" value={employee.employment_type?.replace('_', ' ')} />}
            {employee && (
              <InfoField label="Employment Status" value={
                <span className={`badge badge-${employee.employment_status?.toLowerCase()}`}>{employee.employment_status}</span>
              } />
            )}
            {employee && <InfoField label="Joining Date" value={formatDate(employee.joining_date)} />}
            {employee && <InfoField label="Manager" value={employee.manager ? `${employee.manager.first_name} ${employee.manager.last_name}` : '—'} />}
          </dl>
        </div>

        {employee && (
          <>
            <div className="profile-divider" />

            {!editing ? (
              /* ---- Read mode: personal details ---- */
              <div className="profile-details">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 className="profile-section-title" style={{ marginBottom: 0 }}>My Personal Details</h3>
                  <button className="btn btn-primary btn-sm" onClick={startEdit}>Edit My Details</button>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6, marginBottom: 12 }}>
                  Keep your personal, emergency, statutory and bank details up to date.
                </p>
                <dl className="profile-fields">
                  <InfoField label="Phone" value={employee.phone} />
                  <InfoField label="Date of Birth" value={formatDate(employee.date_of_birth)} />
                  <InfoField label="Gender" value={employee.gender ? employee.gender.replace('_', ' ') : '—'} />
                  <InfoField label="Address" value={employee.address} />
                  <InfoField label="Emergency Contact" value={employee.emergency_contact_name} />
                  <InfoField label="Emergency Phone" value={employee.emergency_contact_phone} />
                  <InfoField label="Aadhaar Number" value={employee.aadhaar_number} />
                  <InfoField label="PAN Number" value={employee.pan_number} />
                  <InfoField label="UAN (PF)" value={employee.uan_number} />
                  <InfoField label="ESI Number" value={employee.esi_number} />
                  <InfoField label="Bank Name" value={employee.bank_name} />
                  <InfoField label="Account Holder" value={employee.bank_account_holder_name} />
                  <InfoField label="Account Number" value={employee.bank_account_number} />
                  <InfoField label="IFSC Code" value={employee.bank_ifsc_code} />
                </dl>
              </div>
            ) : (
              /* ---- Edit mode: personal details ---- */
              form && (
                <form className="profile-details employee-form" onSubmit={handleSave}>
                  <h3 className="profile-section-title">Edit My Personal Details</h3>

                  <h4 className="form-section-title" style={{ fontSize: 14, marginTop: 8 }}>Personal</h4>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Phone</label>
                      <input className="form-input" value={form.phone} onChange={set('phone')} placeholder="+91 9999999999" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Date of Birth</label>
                      <input type="date" className="form-input" value={form.date_of_birth} onChange={set('date_of_birth')} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Gender</label>
                      <select className="form-input" value={form.gender} onChange={set('gender')}>
                        <option value="">Select gender</option>
                        <option value="MALE">Male</option>
                        <option value="FEMALE">Female</option>
                        <option value="OTHER">Other</option>
                        <option value="PREFER_NOT_TO_SAY">Prefer not to say</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Address</label>
                    <textarea className="form-input" rows={3} value={form.address} onChange={set('address')} placeholder="Full address" />
                  </div>

                  <h4 className="form-section-title" style={{ fontSize: 14, marginTop: 16 }}>Emergency Contact</h4>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Contact Name</label>
                      <input className="form-input" value={form.emergency_contact_name} onChange={set('emergency_contact_name')} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Contact Phone</label>
                      <input className="form-input" value={form.emergency_contact_phone} onChange={set('emergency_contact_phone')} />
                    </div>
                  </div>

                  <h4 className="form-section-title" style={{ fontSize: 14, marginTop: 16 }}>Statutory Details</h4>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Aadhaar Number</label>
                      <input className={`form-input${errors.aadhaar_number ? ' input-error' : ''}`} value={form.aadhaar_number} onChange={set('aadhaar_number')} placeholder="123412341234" maxLength={12} inputMode="numeric" />
                      {errors.aadhaar_number && <span className="field-error">{errors.aadhaar_number}</span>}
                    </div>
                    <div className="form-group">
                      <label className="form-label">PAN Number</label>
                      <input className={`form-input${errors.pan_number ? ' input-error' : ''}`} value={form.pan_number} onChange={set('pan_number')} placeholder="ABCDE1234F" maxLength={10} style={{ textTransform: 'uppercase' }} />
                      {errors.pan_number && <span className="field-error">{errors.pan_number}</span>}
                    </div>
                    <div className="form-group">
                      <label className="form-label">UAN (PF)</label>
                      <input className={`form-input${errors.uan_number ? ' input-error' : ''}`} value={form.uan_number} onChange={set('uan_number')} placeholder="100123456789" maxLength={12} inputMode="numeric" />
                      {errors.uan_number && <span className="field-error">{errors.uan_number}</span>}
                    </div>
                    <div className="form-group">
                      <label className="form-label">ESI Number</label>
                      <input className="form-input" value={form.esi_number} onChange={set('esi_number')} placeholder="ESI IP number" maxLength={20} />
                    </div>
                  </div>

                  <h4 className="form-section-title" style={{ fontSize: 14, marginTop: 16 }}>Bank Details</h4>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Bank Name</label>
                      <input className="form-input" value={form.bank_name} onChange={set('bank_name')} placeholder="e.g. HDFC Bank" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Account Holder Name</label>
                      <input className="form-input" value={form.bank_account_holder_name} onChange={set('bank_account_holder_name')} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Account Number</label>
                      <input className="form-input" value={form.bank_account_number} onChange={set('bank_account_number')} maxLength={20} inputMode="numeric" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">IFSC Code</label>
                      <input className={`form-input${errors.bank_ifsc_code ? ' input-error' : ''}`} value={form.bank_ifsc_code} onChange={set('bank_ifsc_code')} placeholder="HDFC0001234" maxLength={11} style={{ textTransform: 'uppercase' }} />
                      {errors.bank_ifsc_code && <span className="field-error">{errors.bank_ifsc_code}</span>}
                    </div>
                  </div>

                  <div className="form-actions" style={{ marginTop: 16 }}>
                    <button type="button" className="btn btn-secondary" onClick={cancelEdit} disabled={saving}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={saving}>
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </form>
              )
            )}
          </>
        )}
      </div>

      {/* Change password */}
      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 className="profile-section-title" style={{ marginBottom: 2 }}>Password</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Change the password you use to sign in.</p>
          </div>
          {!pwOpen && (
            <button className="btn btn-secondary" onClick={() => { setPwOpen(true); setPwSuccess(''); setPwErrors({}); }}>
              Change Password
            </button>
          )}
        </div>

        {pwSuccess && <div className="success-message" style={{ marginTop: 12 }}>{pwSuccess}</div>}

        {pwOpen && (
          <form className="employee-form" onSubmit={handleChangePassword} style={{ marginTop: 16 }}>
            {pwErrors._ && <div className="error-message" style={{ marginBottom: 12 }}>{pwErrors._}</div>}
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Current Password</label>
                <input type="password" autoComplete="current-password"
                  className={`form-input${pwErrors.current_password ? ' input-error' : ''}`}
                  value={pwForm.current} onChange={e => { setPwForm(f => ({ ...f, current: e.target.value })); setPwErrors(p => ({ ...p, current_password: '' })); }} />
                {pwErrors.current_password && <span className="field-error">{pwErrors.current_password}</span>}
              </div>
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input type="password" autoComplete="new-password"
                  className={`form-input${pwErrors.new_password ? ' input-error' : ''}`}
                  value={pwForm.next} onChange={e => { setPwForm(f => ({ ...f, next: e.target.value })); setPwErrors(p => ({ ...p, new_password: '' })); }}
                  placeholder="At least 8 characters" />
                {pwErrors.new_password && <span className="field-error">{pwErrors.new_password}</span>}
              </div>
              <div className="form-group">
                <label className="form-label">Confirm New Password</label>
                <input type="password" autoComplete="new-password"
                  className={`form-input${pwErrors.confirm_password ? ' input-error' : ''}`}
                  value={pwForm.confirm} onChange={e => { setPwForm(f => ({ ...f, confirm: e.target.value })); setPwErrors(p => ({ ...p, confirm_password: '' })); }} />
                {pwErrors.confirm_password && <span className="field-error">{pwErrors.confirm_password}</span>}
              </div>
            </div>
            <div className="form-actions" style={{ marginTop: 8 }}>
              <button type="button" className="btn btn-secondary" disabled={pwSaving}
                onClick={() => { setPwOpen(false); setPwForm({ current: '', next: '', confirm: '' }); setPwErrors({}); }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={pwSaving}>
                {pwSaving ? 'Changing...' : 'Update Password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
