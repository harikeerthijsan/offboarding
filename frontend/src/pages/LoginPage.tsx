import { useState, type FormEvent } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import '../styles/login.css';

export default function LoginPage() {
  const { isAuthenticated, login, isLoading } = useAuthContext();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  const busy = submitting || isLoading;
  const emailValid = /\S+@\S+\.\S+/.test(email.trim());

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNotice('');
    if (!email.trim() || !password.trim()) {
      setError('Please enter both your email and password.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; message?: string } } };
      setError(
        axiosErr?.response?.data?.detail ||
        axiosErr?.response?.data?.message ||
        'Invalid credentials. Please try again.'
      );
      setSubmitting(false);
    }
  };

  // Password reset & self sign-up aren't provisioned on the backend.
  const notConfigured = (what: string) => {
    setError('');
    setNotice(`${what} isn’t set up yet. Please sign in with your email, or contact your HR administrator.`);
  };

  return (
    <div className="lg-root">
      <div className="lg-sheen" aria-hidden="true" />

      <form className="lg-form" onSubmit={handleSubmit} noValidate>
        <h1 className="lg-title">Log in</h1>

        {error && <div className="lg-alert lg-alert-error" role="alert">{error}</div>}
        {notice && <div className="lg-alert lg-alert-info" role="status">{notice}</div>}

        {/* Email */}
        <div className="lg-field">
          <span className="lg-ic" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" />
            </svg>
          </span>
          <input
            className="lg-input"
            type="text"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="Email address"
            autoComplete="username"
            disabled={busy}
          />
          <span className={`lg-status${emailValid ? ' is-ok' : ''}`} aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><path d="m8.5 12 2.5 2.5 4.5-5" />
            </svg>
          </span>
        </div>

        {/* Password */}
        <div className="lg-field">
          <span className="lg-ic" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4.5" y="10.5" width="15" height="10" rx="2" /><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
            </svg>
          </span>
          <input
            className="lg-input"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete="current-password"
            disabled={busy}
          />
          <button type="button" className="lg-forgot" onClick={() => notConfigured('Password reset')} disabled={busy}>
            Forgot?
          </button>
          <button
            type="button"
            className="lg-eye"
            onClick={() => setShowPassword(s => !s)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            aria-pressed={showPassword}
            disabled={busy}
          >
            {showPassword ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9.88 9.88a3 3 0 0 0 4.24 4.24" /><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.5 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                <path d="M6.61 6.61A13.5 13.5 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61" /><line x1="2" y1="2" x2="22" y2="22" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>

        <button type="submit" className="lg-submit" disabled={busy}>
          {busy ? <><span className="lg-spinner" aria-hidden="true" /> Signing in…</> : 'Login to your account'}
        </button>

        <div className="lg-row">
          <label className="lg-remember">
            <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} disabled={busy} />
            <span className="lg-radio" aria-hidden="true" />
            <span>Remember me</span>
          </label>
          <p className="lg-signup">
            New here? <button type="button" className="lg-link" onClick={() => notConfigured('Self sign-up')}>Sign in!</button>
          </p>
        </div>
      </form>
    </div>
  );
}
