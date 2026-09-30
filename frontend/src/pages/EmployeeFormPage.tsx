import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { employeeService } from '../services/employeeService';
import type { Department, Designation, Employee } from '../types';

interface FormData {
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  gender: string;
  department_id: string;
  designation_id: string;
  manager_id: string;
  joining_date: string;
  employment_type: string;
  employment_status: string;
  location: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
}

const emptyForm: FormData = {
  employee_id: '', first_name: '', last_name: '', email: '', phone: '',
  date_of_birth: '', gender: '', department_id: '', designation_id: '',
  manager_id: '', joining_date: '', employment_type: 'FULL_TIME',
  employment_status: 'ACTIVE', location: '', address: '',
  emergency_contact_name: '', emergency_contact_phone: '',
};

export default function EmployeeFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = !!id;

  const [form, setForm] = useState<FormData>(emptyForm);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [managers, setManagers] = useState<Array<{ id: number; employee_id: string; first_name: string; last_name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEdit);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState('');
  const [apiError, setApiError] = useState('');

  useEffect(() => {
    employeeService.getDepartments({ is_active: true }).then(r => setDepartments(r.results)).catch(() => {});
    employeeService.getEmployees({ status: 'ACTIVE' }).then(r => setManagers(r.results)).catch(() => {});
    if (isEdit && id) {
      employeeService.getEmployee(Number(id)).then((emp: Employee) => {
        setForm({
          employee_id: emp.employee_id,
          first_name: emp.first_name,
          last_name: emp.last_name,
          email: emp.email,
          phone: emp.phone || '',
          date_of_birth: emp.date_of_birth || '',
          gender: emp.gender || '',
          department_id: emp.department?.id?.toString() || '',
          designation_id: emp.designation?.id?.toString() || '',
          manager_id: emp.manager?.id?.toString() || '',
          joining_date: emp.joining_date,
          employment_type: emp.employment_type,
          employment_status: emp.employment_status,
          location: emp.location || '',
          address: emp.address || '',
          emergency_contact_name: emp.emergency_contact_name || '',
          emergency_contact_phone: emp.emergency_contact_phone || '',
        });
        if (emp.department?.id) {
          employeeService.getDesignations({ department: emp.department.id }).then(r => setDesignations(r.results));
        }
      }).catch(() => {}).finally(() => setFetching(false));
    }
  }, [isEdit, id]);

  useEffect(() => {
    if (form.department_id) {
      employeeService.getDesignations({ department: Number(form.department_id) }).then(r => setDesignations(r.results)).catch(() => setDesignations([]));
    } else {
      setDesignations([]);
    }
  }, [form.department_id]);

  const set = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm(f => ({ ...f, [field]: e.target.value }));
    setErrors(prev => ({ ...prev, [field]: '' }));
  };

  const validate = (): boolean => {
    const e: Record<string, string> = {};
    if (!form.employee_id.trim()) e.employee_id = 'Employee ID is required';
    if (!form.first_name.trim()) e.first_name = 'First name is required';
    if (!form.last_name.trim()) e.last_name = 'Last name is required';
    if (!form.email.trim()) e.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Enter a valid email';
    if (!form.joining_date) e.joining_date = 'Joining date is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setApiError('');
    setSuccess('');
    const payload: Record<string, unknown> = {
      employee_id: form.employee_id,
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      phone: form.phone || '',
      date_of_birth: form.date_of_birth || null,
      gender: form.gender || '',
      department_id: form.department_id ? Number(form.department_id) : null,
      designation_id: form.designation_id ? Number(form.designation_id) : null,
      manager_id: form.manager_id ? Number(form.manager_id) : null,
      joining_date: form.joining_date,
      employment_type: form.employment_type,
      employment_status: form.employment_status,
      location: form.location || '',
      address: form.address || '',
      emergency_contact_name: form.emergency_contact_name || '',
      emergency_contact_phone: form.emergency_contact_phone || '',
    };
    try {
      let result: Employee;
      if (isEdit && id) {
        result = await employeeService.updateEmployee(Number(id), payload);
      } else {
        setApiError('To create an employee, a user account must be created first via Admin. This flow will be improved in a future phase.');
        setLoading(false);
        return;
      }
      setSuccess('Employee updated successfully.');
      setTimeout(() => navigate(`/employees/${result.id}`), 1000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: Record<string, string[]> } };
      if (axiosErr.response?.data) {
        const data = axiosErr.response.data;
        const fieldErrors: Record<string, string> = {};
        Object.entries(data).forEach(([k, v]) => { fieldErrors[k] = Array.isArray(v) ? v[0] : String(v); });
        setErrors(fieldErrors);
        setApiError('Please correct the errors below.');
      } else {
        setApiError('An error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (fetching) return <div className="loading-state" style={{ minHeight: 300 }}><div className="spinner" /></div>;

  return (
    <div className="form-page">
      <div className="page-header">
        <h1 className="page-title">{isEdit ? 'Edit Employee' : 'Add Employee'}</h1>
        <button className="btn btn-secondary" onClick={() => navigate(isEdit ? `/employees/${id}` : '/employees')}>Cancel</button>
      </div>

      {success && <div className="success-message">{success}</div>}
      {apiError && <div className="error-message" style={{ marginBottom: 16 }}>{apiError}</div>}

      <form onSubmit={handleSubmit} className="employee-form">
        <div className="form-section">
          <h3 className="form-section-title">Basic Information</h3>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Employee ID *</label>
              <input className={`form-input${errors.employee_id ? ' input-error' : ''}`} value={form.employee_id} onChange={set('employee_id')} placeholder="EMP001" disabled={isEdit} />
              {errors.employee_id && <span className="field-error">{errors.employee_id}</span>}
            </div>
            <div className="form-group">
              <label className="form-label">First Name *</label>
              <input className={`form-input${errors.first_name ? ' input-error' : ''}`} value={form.first_name} onChange={set('first_name')} />
              {errors.first_name && <span className="field-error">{errors.first_name}</span>}
            </div>
            <div className="form-group">
              <label className="form-label">Last Name *</label>
              <input className={`form-input${errors.last_name ? ' input-error' : ''}`} value={form.last_name} onChange={set('last_name')} />
              {errors.last_name && <span className="field-error">{errors.last_name}</span>}
            </div>
            <div className="form-group">
              <label className="form-label">Email *</label>
              <input type="email" className={`form-input${errors.email ? ' input-error' : ''}`} value={form.email} onChange={set('email')} />
              {errors.email && <span className="field-error">{errors.email}</span>}
            </div>
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
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Employment Details</h3>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Joining Date *</label>
              <input type="date" className={`form-input${errors.joining_date ? ' input-error' : ''}`} value={form.joining_date} onChange={set('joining_date')} />
              {errors.joining_date && <span className="field-error">{errors.joining_date}</span>}
            </div>
            <div className="form-group">
              <label className="form-label">Employment Type</label>
              <select className="form-input" value={form.employment_type} onChange={set('employment_type')}>
                <option value="FULL_TIME">Full Time</option>
                <option value="PART_TIME">Part Time</option>
                <option value="CONTRACT">Contract</option>
                <option value="INTERN">Intern</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Status</label>
              <select className="form-input" value={form.employment_status} onChange={set('employment_status')}>
                <option value="ACTIVE">Active</option>
                <option value="OFFBOARDING">Offboarding</option>
                <option value="EXITED">Exited</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Department</label>
              <select className="form-input" value={form.department_id} onChange={set('department_id')}>
                <option value="">Select department</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Designation</label>
              <select className="form-input" value={form.designation_id} onChange={set('designation_id')} disabled={!form.department_id}>
                <option value="">{form.department_id ? 'Select designation' : 'Select department first'}</option>
                {designations.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Manager</label>
              <select className="form-input" value={form.manager_id} onChange={set('manager_id')}>
                <option value="">No manager</option>
                {managers.filter(m => !isEdit || m.id !== Number(id)).map(m => (
                  <option key={m.id} value={m.id}>{m.first_name} {m.last_name} ({m.employee_id})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="form-input" value={form.location} onChange={set('location')} placeholder="City, Office" />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Address</label>
            <textarea className="form-input" rows={3} value={form.address} onChange={set('address')} placeholder="Full address" />
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Emergency Contact</h3>
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
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Employee'}
          </button>
        </div>
      </form>
    </div>
  );
}
