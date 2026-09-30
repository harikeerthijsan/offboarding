import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { dashboardService, type DashboardOverview } from '../services/dashboardService';
import Icon, { type IconName } from '../components/Icon';
import { formatDate } from '../utils/kt';

const STAT_TILES: { key: keyof DashboardOverview['stats']; label: string; icon: IconName; color: string; bg: string }[] = [
  { key: 'total_employees', label: 'Total Employees', icon: 'users', color: '#0d5aa7', bg: '#e7f1fb' },
  { key: 'active', label: 'Active Employees', icon: 'user-check', color: '#16a34a', bg: '#e7f7ee' },
  { key: 'offboarding', label: 'Serving Notice Period', icon: 'clock', color: '#ea580c', bg: '#fdeee3' },
  { key: 'exited', label: 'Exited Employees', icon: 'logout', color: '#7c3aed', bg: '#f0e9fd' },
  { key: 'departments', label: 'Departments', icon: 'building', color: '#0891b2', bg: '#e2f4f8' },
];

function TrendChart({ t }: { t: DashboardOverview['trends'] }) {
  const W = 680, H = 230, padL = 30, padR = 12, padT = 12, padB = 26;
  const n = t.labels.length;
  const max = Math.max(5, ...t.new, ...t.completed, ...t.pending);
  const x = (i: number) => padL + (i * (W - padL - padR)) / Math.max(1, n - 1);
  const y = (v: number) => padT + (1 - v / max) * (H - padT - padB);
  const series = [
    { data: t.new, color: '#0d5aa7', fill: 'rgba(13,90,167,0.10)' },
    { data: t.completed, color: '#16a34a', fill: 'rgba(22,163,74,0.12)' },
    { data: t.pending, color: '#ea580c', fill: 'none' },
  ];
  const line = (dd: number[]) => dd.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(v)}`).join(' ');
  const area = (dd: number[]) => `${line(dd)} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const ticks = [0, Math.round(max / 2), max];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      {ticks.map((tk, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={y(tk)} y2={y(tk)} stroke="#eef1f5" strokeWidth="1" />
          <text x={padL - 6} y={y(tk) + 3} textAnchor="end" fontSize="10" fill="#98a2b3">{tk}</text>
        </g>
      ))}
      {series.map((s, si) => s.fill !== 'none' && (
        <path key={`a${si}`} d={area(s.data)} fill={s.fill} stroke="none" />
      ))}
      {series.map((s, si) => (
        <path key={`l${si}`} d={line(s.data)} fill="none" stroke={s.color} strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {series.map((s, si) => s.data.map((v, i) => (
        <circle key={`p${si}-${i}`} cx={x(i)} cy={y(v)} r="3" fill="#fff" stroke={s.color} strokeWidth="2" />
      )))}
      {t.labels.map((lbl, i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="#98a2b3">{lbl}</text>
      ))}
    </svg>
  );
}

export default function DashboardPage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [d, setD] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    dashboardService.overview().then(setD).catch(() => setError('Failed to load dashboard.')).finally(() => setLoading(false));
  }, []);

  const name = user?.first_name || user?.username || 'there';
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' });

  if (loading) return <div className="loading-state"><div className="spinner" /><p>Loading dashboard…</p></div>;
  if (error || !d) return <div className="error-message">{error || 'No data.'}</div>;

  const maxDept = Math.max(1, ...d.departments.map(x => x.count));
  const deptColors = ['#0d5aa7', '#7c3aed', '#e11d48', '#ea580c', '#f59e0b', '#0891b2', '#16a34a', '#64748b'];

  return (
    <div className="dash">
      {/* Welcome header */}
      <div className="dash-welcome-row">
        <div>
          <h1 className="dash-hello">Welcome back, {name}!</h1>
          <p className="dash-sub">Here's an overview of employee offboarding activities.</p>
        </div>
        <div className="dash-welcome-actions">
          <span className="date-chip"><Icon name="calendar" size={15} /> {today}</span>
          <button className="btn btn-primary" onClick={() => navigate('/offboarding/create')}>
            <Icon name="plus" size={16} /> New Offboarding
          </button>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="dstat-grid">
        {STAT_TILES.map(tile => {
          const m = d.stats[tile.key];
          const up = m.trend > 0, flat = m.trend === 0;
          return (
            <div className="dstat" key={tile.key}>
              <div className="dstat-icon" style={{ background: tile.bg, color: tile.color }}>
                <Icon name={tile.icon} size={22} />
              </div>
              <div className="dstat-body">
                <div className="dstat-label">{tile.label}</div>
                <div className="dstat-value">{m.value}</div>
                <div className={`dstat-trend ${flat ? 'flat' : up ? 'up' : 'down'}`}>
                  {flat ? '—' : <Icon name={up ? 'arrow-up' : 'arrow-down'} size={13} />}
                  {flat ? 'No change' : `${up ? '+' : ''}${m.trend}%`} <span>vs last month</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dept overview + recent activity + upcoming tasks */}
      <div className="dash-row dash-row-3">
        <div className="card">
          <h3>Department Overview</h3>
          {d.departments.map((dep, i) => (
            <div className="dept-bar-row" key={dep.name}>
              <span className="dept-bar-name">{dep.name}</span>
              <span className="dept-bar-track">
                <span className="dept-bar-fill" style={{ width: `${(dep.count / maxDept) * 100}%`, background: deptColors[i % deptColors.length] }} />
              </span>
              <span className="dept-bar-count">{dep.count}</span>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-h-flex"><h3>Recent Exits</h3><button className="link-btn" onClick={() => navigate('/hr/offboarding')}>View All</button></div>
          {d.recent_exits.length === 0 && <p className="muted">No recent exits.</p>}
          {d.recent_exits.map((e, i) => (
            <div className="act-row" key={i}>
              <span className="act-icon" style={{ background: '#f0e9fd', color: '#7c3aed' }}><Icon name="logout" size={16} /></span>
              <div className="act-body">
                <div className="act-title">{e.name}</div>
                <div className="act-target">{e.employee_id}{e.department ? ` · ${e.department}` : ''}</div>
              </div>
              <span className="act-when">{formatDate(e.date)}</span>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-h-flex"><h3>Upcoming Tasks</h3><button className="link-btn" onClick={() => navigate('/hr/offboarding')}>View All</button></div>
          {d.upcoming_tasks.length === 0 && <p className="muted">No pending action items.</p>}
          {d.upcoming_tasks.map((t, i) => (
            <div className="task-row" key={i}>
              <div className="task-body">
                <div className="task-title">{t.title}</div>
                <div className="task-sub">{t.subtitle}</div>
              </div>
              <div className="task-meta">
                {t.due && <span className="task-due">{formatDate(t.due)}</span>}
                <span className={`badge task-${t.priority.toLowerCase()}`}>{t.priority.charAt(0) + t.priority.slice(1).toLowerCase()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Trends + quick actions */}
      <div className="dash-row dash-row-trend">
        <div className="card">
          <div className="card-h-flex">
            <h3>Offboarding Trends (Last 6 Months)</h3>
            <div className="trend-legend">
              <span><i style={{ background: '#0d5aa7' }} />New</span>
              <span><i style={{ background: '#16a34a' }} />Completed</span>
              <span><i style={{ background: '#ea580c' }} />Pending</span>
            </div>
          </div>
          <TrendChart t={d.trends} />
        </div>

        <div className="card">
          <h3>Quick Actions</h3>
          <div className="qa-grid">
            <button className="qa-btn qa-blue" onClick={() => navigate('/offboarding/create')}><Icon name="plus" size={18} /> New Offboarding</button>
            <button className="qa-btn qa-green" onClick={() => navigate('/offboarding')}><Icon name="file" size={18} /> Generate Document</button>
            <button className="qa-btn qa-rose" onClick={() => navigate('/employees')}><Icon name="users" size={18} /> Manage Employees</button>
            <button className="qa-btn qa-amber" onClick={() => navigate('/hr/offboarding')}><Icon name="bar-chart" size={18} /> View Reports</button>
          </div>
        </div>
      </div>
    </div>
  );
}
