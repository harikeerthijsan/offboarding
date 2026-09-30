import { useState, type FormEvent } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import '../styles/login.css';

export default function LoginPage() {
  const { isAuthenticated, login, isLoading } = useAuthContext();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; message?: string } } };
      const msg =
        axiosErr?.response?.data?.detail ||
        axiosErr?.response?.data?.message ||
        'Invalid credentials. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const busy = submitting || isLoading;

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-header">
            <img src="/jsanlogo.png" alt="JSAN" className="login-logo" />
            <h1>Employee Offboarding</h1>
            <p>Sign in to your account to continue</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            {error && <div className="error-message">{error}</div>}

            <div className="form-group">
              <label className="form-label" htmlFor="email">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                className="form-input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
                required
                disabled={busy}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="form-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
                disabled={busy}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary login-submit"
              disabled={busy}
            >
              {busy ? (
                <>
                  <span className="btn-spinner" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="login-footer">
            <p>Employee Offboarding Management System</p>
          </div>
        </div>
      </div>
    </div>
  );
}
