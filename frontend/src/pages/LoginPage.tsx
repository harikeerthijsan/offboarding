import { useState, useRef, useEffect, useMemo, useCallback, type FormEvent } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import '../styles/login.css';

/* ── Local inline icons (stroke = currentColor), consistent with the app set ── */
type IconKey = 'people' | 'goals' | 'learning' | 'hrops' | 'experience' | 'eye' | 'eye-off' | 'arrow';
const ICONS: Record<IconKey, JSX.Element> = {
  people: (<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>),
  goals: (<><path d="M3 3v18h18" /><rect x="7" y="12" width="3" height="5" rx="0.5" /><rect x="12" y="8" width="3" height="9" rx="0.5" /><rect x="17" y="5" width="3" height="12" rx="0.5" /></>),
  learning: (<><path d="M22 10 12 5 2 10l10 5 10-5Z" /><path d="M6 12v5c0 1 2.5 3 6 3s6-2 6-3v-5" /></>),
  hrops: (<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" /></>),
  experience: (<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78Z" />),
  eye: (<><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>),
  'eye-off': (<><path d="M9.88 9.88a3 3 0 0 0 4.24 4.24" /><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.5 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" /><path d="M6.61 6.61A13.5 13.5 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61" /><line x1="2" y1="2" x2="22" y2="22" /></>),
  arrow: (<><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>),
};

function Svg({ icon, size = 20 }: { icon: IconKey; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {ICONS[icon]}
    </svg>
  );
}

const FEATURES: { key: IconKey; label: string; sub: string; cls: string }[] = [
  { key: 'people',     label: 'People Management',     sub: 'Profiles & org', cls: 'fc-1' },
  { key: 'goals',      label: 'Performance & Goals',   sub: 'OKRs & reviews', cls: 'fc-2' },
  { key: 'learning',   label: 'Learning & Development', sub: 'Skills & growth', cls: 'fc-3' },
  { key: 'hrops',      label: 'HR Operations',         sub: 'Workflows',      cls: 'fc-4' },
  { key: 'experience', label: 'Employee Experience',   sub: 'Engagement',     cls: 'fc-5' },
];

const STATS = [
  { value: '10K+', label: 'People Connected' },
  { value: '95%', label: 'Love Their Workday' },
  { value: '3x', label: 'Faster Workflows' },
];

/* Words that rotate at the end of the headline. */
const CYCLE_WORDS = ['Growth.', 'Potential.', 'Performance.', 'Possibility.', 'Belonging.'];

/* People-nodes orbiting the central hub (positions in % of the hub box). */
const HUB_NODES = Array.from({ length: 6 }, (_, i) => {
  const a = ((i * 60 - 90) * Math.PI) / 180;
  return {
    x: +(50 + 40 * Math.cos(a)).toFixed(2),
    y: +(50 + 40 * Math.sin(a)).toFixed(2),
    icon: (['people', 'goals', 'learning', 'experience', 'hrops', 'people'] as IconKey[])[i],
  };
});

/* Faint HR-themed glyphs drifting in the background (on-brand, not decoration-for-its-own-sake). */
const GLYPHS: { key: IconKey; left: number; top: number; size: number; depth: number; dur: number; delay: number }[] = [
  { key: 'people',     left: 8,  top: 20, size: 30, depth: 20, dur: 13, delay: 0 },
  { key: 'goals',      left: 40, top: 12, size: 24, depth: 30, dur: 16, delay: 1.5 },
  { key: 'learning',   left: 18, top: 62, size: 28, depth: 24, dur: 15, delay: 3 },
  { key: 'experience', left: 52, top: 70, size: 22, depth: 34, dur: 12, delay: 2 },
  { key: 'hrops',      left: 60, top: 40, size: 26, depth: 28, dur: 17, delay: 4 },
  { key: 'people',     left: 30, top: 88, size: 20, depth: 38, dur: 14, delay: 0.8 },
];

export default function LoginPage() {
  const { isAuthenticated, login, isLoading } = useAuthContext();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [wordIdx, setWordIdx] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const target = useRef({ x: 0, y: 0 });
  const current = useRef({ x: 0, y: 0 });

  // Deterministic-ish particle field, computed once.
  const particles = useMemo(
    () => Array.from({ length: 22 }, (_, i) => ({
      left: (i * 37.3) % 100,
      top: (i * 61.7) % 100,
      size: 1.5 + ((i * 7) % 4),
      delay: ((i * 13) % 100) / 10,
      dur: 9 + ((i * 17) % 11),
      depth: 6 + ((i * 11) % 18),
      opacity: 0.25 + ((i * 29) % 45) / 100,
    })),
    []
  );

  // Connection constellation — "people" nodes linked when close (People Connected).
  const net = useMemo(() => {
    const W = 1000, H = 600;
    const nodes = Array.from({ length: 16 }, (_, i) => ({
      x: ((i * 173 + 90) % W),
      y: ((i * 229 + 60) % H),
      delay: (i * 0.4) % 4,
    }));
    const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        const dx = nodes[a].x - nodes[b].x, dy = nodes[a].y - nodes[b].y;
        if (Math.hypot(dx, dy) < 260) {
          edges.push({ x1: nodes[a].x, y1: nodes[a].y, x2: nodes[b].x, y2: nodes[b].y });
        }
      }
    }
    return { W, H, nodes, edges };
  }, []);

  // Smooth cursor-driven parallax → CSS vars on the root (no re-render).
  const prefersReduced = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  );

  useEffect(() => {
    if (prefersReduced) return;
    const el = rootRef.current;
    if (!el) return;

    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      target.current.x = ((e.clientX - r.left) / r.width - 0.5) * 2;   // -1 .. 1
      target.current.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    };
    const onLeave = () => { target.current.x = 0; target.current.y = 0; };

    const tick = () => {
      current.current.x += (target.current.x - current.current.x) * 0.06;
      current.current.y += (target.current.y - current.current.y) * 0.06;
      el.style.setProperty('--mx', current.current.x.toFixed(4));
      el.style.setProperty('--my', current.current.y.toFixed(4));
      rafRef.current = requestAnimationFrame(tick);
    };

    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [prefersReduced]);

  // Rotate the headline word (skipped under reduced-motion → stays on the first).
  useEffect(() => {
    if (prefersReduced) return;
    const id = window.setInterval(() => {
      setWordIdx(i => (i + 1) % CYCLE_WORDS.length);
    }, 2400);
    return () => window.clearInterval(id);
  }, [prefersReduced]);

  // Cursor spotlight on the login card.
  const onCardMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (prefersReduced) return;
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--sx', `${((e.clientX - r.left) / r.width) * 100}%`);
    e.currentTarget.style.setProperty('--sy', `${((e.clientY - r.top) / r.height) * 100}%`);
  }, [prefersReduced]);

  // Per-card interactive 3D tilt (the "playable" feature cards).
  const onTilt = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (prefersReduced) return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    e.currentTarget.style.setProperty('--rx', `${(-py * 16).toFixed(2)}deg`);
    e.currentTarget.style.setProperty('--ry', `${(px * 18).toFixed(2)}deg`);
    e.currentTarget.style.setProperty('--gx', `${(px * 100 + 50).toFixed(1)}%`);
    e.currentTarget.style.setProperty('--gy', `${(py * 100 + 50).toFixed(1)}%`);
  }, [prefersReduced]);
  const onTiltReset = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.setProperty('--rx', '0deg');
    e.currentTarget.style.setProperty('--ry', '0deg');
  }, []);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNotice('');
    if (!email.trim() || !password.trim()) {
      setError('Please enter both your email/employee ID and password.');
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
    } finally {
      setSubmitting(false);
    }
  };

  const busy = submitting || isLoading;
  const forgotPassword = () => {
    setError('');
    setNotice('To reset your password, please contact your HR administrator.');
  };

  return (
    <div className="lx-root" ref={rootRef}>
      {/* ── Ambient background layers ── */}
      <div className="lx-bg" aria-hidden="true">
        <div className="lx-bg-grad" />
        <div className="lx-streaks" />

        {/* People-connection constellation */}
        <svg className="lx-net" viewBox={`0 0 ${net.W} ${net.H}`} preserveAspectRatio="xMidYMid slice">
          <g className="lx-net-lines">
            {net.edges.map((e, i) => (
              <line key={i} className="lx-net-line" x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} />
            ))}
          </g>
          <g className="lx-net-nodes">
            {net.nodes.map((n, i) => (
              <circle key={i} className="lx-net-node" cx={n.x} cy={n.y} r={3}
                style={{ animationDelay: `${n.delay}s` }} />
            ))}
          </g>
        </svg>

        {/* Drifting HR-themed glyphs */}
        <div className="lx-glyphs">
          {GLYPHS.map((g, i) => (
            <span
              key={i}
              className="lx-glyph"
              style={{
                left: `${g.left}%`,
                top: `${g.top}%`,
                animationDuration: `${g.dur}s`,
                animationDelay: `${g.delay}s`,
                ['--depth' as string]: g.depth,
              }}
            >
              <Svg icon={g.key} size={g.size} />
            </span>
          ))}
        </div>

        <div className="lx-city" />
        <div className="lx-particles">
          {particles.map((p, i) => (
            <span
              key={i}
              className="lx-particle"
              style={{
                left: `${p.left}%`,
                top: `${p.top}%`,
                width: p.size,
                height: p.size,
                opacity: p.opacity,
                animationDelay: `${p.delay}s`,
                animationDuration: `${p.dur}s`,
                ['--depth' as string]: p.depth,
              }}
            />
          ))}
        </div>
      </div>

      <div className="lx-content">
        {/* ── Left: animated brand experience ── */}
        <section className="lx-brand" aria-label="JSAN People360">
          <header className="lx-brand-head">
            <span className="lx-word">JSAN<b>People360</b></span>
          </header>

          <div className="lx-hero">
            <h1 className="lx-headline">
              Where people<br />come first, and<br />everyone enables{' '}
              <span className="lx-cycle">
                <span className="lx-grad-text lx-cycle-word" key={wordIdx}>{CYCLE_WORDS[wordIdx]}</span>
              </span>
            </h1>
          </div>

          {/* Globe + interactive feature cards */}
          <div className="lx-stage">
            <div className="lx-orbit lx-orbit-a" aria-hidden="true" />
            <div className="lx-orbit lx-orbit-b" aria-hidden="true" />
            <div className="lx-orbit lx-orbit-c" aria-hidden="true" />

            <div className="lx-hub">
              <svg className="lx-hub-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                {HUB_NODES.map((n, i) => (
                  <line key={i} className="lx-hub-link" x1="50" y1="50" x2={n.x} y2={n.y}
                    style={{ animationDelay: `${(i * 0.4).toFixed(1)}s` }} />
                ))}
              </svg>

              {HUB_NODES.map((n, i) => (
                <div
                  key={i}
                  className="lx-node"
                  style={{ left: `${n.x}%`, top: `${n.y}%`, animationDelay: `${((i * 0.7) % 4).toFixed(1)}s` }}
                >
                  <Svg icon={n.icon} size={18} />
                </div>
              ))}

              <div className="lx-core">
                <span className="lx-core-ring" aria-hidden="true" />
                <span className="lx-core-ic"><Svg icon="people" size={22} /></span>
                <span className="lx-core-tx">People<b>360°</b></span>
              </div>
            </div>

            {FEATURES.map(f => (
              <div className={`lx-fpos ${f.cls}`} key={f.key}>
                <div className="lx-fcard" onMouseMove={onTilt} onMouseLeave={onTiltReset}>
                  <span className="lx-fcard-hl" aria-hidden="true" />
                  <span className="lx-fcard-ic"><Svg icon={f.key} size={15} /></span>
                  <span className="lx-fcard-tx">{f.label}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="lx-stats">
            {STATS.map(s => (
              <div className="lx-stat" key={s.label}>
                <span className="lx-stat-v">{s.value}</span>
                <span className="lx-stat-l">{s.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Right: login form ── */}
        <section className="lx-auth">
          <div className="lx-card" onMouseMove={onCardMove}>
            <div className="lx-card-spot" aria-hidden="true" />
            <div className="lx-card-inner">
              <h2 className="lx-welcome">
                Welcome to <span className="lx-grad-text">JSAN People360</span>
              </h2>
              <p className="lx-welcome-sub">Sign in to access your workspace</p>

              <form className="lx-form" onSubmit={handleSubmit} noValidate>
                {error && <div className="lx-alert lx-alert-error" role="alert">{error}</div>}
                {notice && <div className="lx-alert lx-alert-info" role="status">{notice}</div>}

                <div className="lx-field">
                  <label htmlFor="login-id">Email or Employee ID</label>
                  <input
                    id="login-id"
                    type="text"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="Enter your email or employee ID"
                    autoComplete="username"
                    required
                    disabled={busy}
                  />
                </div>

                <div className="lx-field">
                  <label htmlFor="login-pass">Password</label>
                  <div className="lx-pass">
                    <input
                      id="login-pass"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      autoComplete="current-password"
                      required
                      disabled={busy}
                    />
                    <button
                      type="button"
                      className="lx-pass-toggle"
                      onClick={() => setShowPassword(s => !s)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                      disabled={busy}
                    >
                      <Svg icon={showPassword ? 'eye-off' : 'eye'} size={18} />
                    </button>
                  </div>
                </div>

                <div className="lx-row">
                  <label className="lx-check">
                    <input
                      type="checkbox"
                      checked={keepSignedIn}
                      onChange={e => setKeepSignedIn(e.target.checked)}
                      disabled={busy}
                    />
                    <span>Keep me signed in</span>
                  </label>
                  <button type="button" className="lx-link" onClick={forgotPassword} disabled={busy}>
                    Forgot Password?
                  </button>
                </div>

                <button type="submit" className="lx-submit" disabled={busy}>
                  <span className="lx-submit-shine" aria-hidden="true" />
                  {busy ? (
                    <><span className="lx-spinner" aria-hidden="true" /> Signing in…</>
                  ) : (
                    <>Sign In <Svg icon="arrow" size={18} /></>
                  )}
                </button>

                <p className="lx-foot">
                  New to People360? <button type="button" className="lx-link" onClick={forgotPassword}>Contact your HR administrator.</button>
                </p>
              </form>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
