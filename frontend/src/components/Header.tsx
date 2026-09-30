import { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthContext } from '../contexts/AuthContext';
import { notificationService } from '../services/notificationService';
import type { NotificationItem } from '../types';
import Icon from './Icon';

function timeAgo(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch { return ''; }
}

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/employees': 'Employees',
  '/offboarding': 'Offboarding',
  '/profile': 'My Profile',
};

function getInitials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

export default function Header() {
  const { user, logout } = useAuthContext();
  const location = useLocation();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);
  const [unread, setUnread] = useState(0);
  const [recent, setRecent] = useState<NotificationItem[]>([]);

  const pageTitle = PAGE_TITLES[location.pathname] ?? 'Employee Offboarding';

  const refreshUnread = useCallback(async () => {
    try { setUnread(await notificationService.unreadCount()); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshUnread();
    // Reasonable refresh strategy: poll unread count every 60s (not excessive).
    const t = setInterval(refreshUnread, 60000);
    return () => clearInterval(t);
  }, [user, refreshUnread]);

  async function openBell() {
    const next = !bellOpen;
    setBellOpen(next);
    if (next) {
      try { setRecent(await notificationService.list()); } catch { /* ignore */ }
    }
  }

  async function handleNotifClick(n: NotificationItem) {
    if (!n.is_read) {
      try { await notificationService.markRead(n.id); await refreshUnread(); } catch { /* ignore */ }
    }
    setBellOpen(false);
    if (n.related_offboarding) navigate(`/offboarding/${n.related_offboarding}`);
    else navigate('/notifications');
  }

  async function markAll() {
    try { await notificationService.markAllRead(); await refreshUnread(); setRecent(r => r.map(n => ({ ...n, is_read: true }))); } catch { /* ignore */ }
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setBellOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDropdownOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  const displayName = user
    ? user.first_name
      ? `${user.first_name} ${user.last_name}`.trim()
      : user.username
    : '';

  const initials = user
    ? getInitials(user.first_name || user.username, user.last_name || '')
    : '?';

  return (
    <header className="header">
      <div className="header-title">{pageTitle}</div>
      <div className="header-actions">
        {user && (
          <div className="bell-wrapper" ref={bellRef}>
            <button className="bell-btn" onClick={openBell} aria-label="Notifications">
              <Icon name="bell" size={20} />
              {unread > 0 && <span className="bell-badge">{unread > 99 ? '99+' : unread}</span>}
            </button>
            {bellOpen && (
              <div className="bell-dropdown">
                <div className="bell-header">
                  <span>Notifications</span>
                  <button className="btn btn-ghost" onClick={markAll} style={{ fontSize: 12 }}>Mark all read</button>
                </div>
                {recent.length === 0 ? (
                  <div style={{ padding: 16, color: 'var(--text-secondary)', fontSize: 13 }}>No notifications.</div>
                ) : (
                  recent.slice(0, 8).map(n => (
                    <div key={n.id} className={`bell-item${n.is_read ? '' : ' unread'}`} onClick={() => handleNotifClick(n)}>
                      <div className="bt">{n.title}</div>
                      <div className="bm">{n.message}</div>
                      <div className="btime">{timeAgo(n.created_at)}</div>
                    </div>
                  ))
                )}
                <div className="bell-item" style={{ textAlign: 'center', color: 'var(--primary)' }}
                  onClick={() => { setBellOpen(false); navigate('/notifications'); }}>
                  View all
                </div>
              </div>
            )}
          </div>
        )}
        {user && (
          <div className="user-dropdown-wrapper" ref={dropdownRef}>
            <button
              className="user-dropdown-trigger"
              onClick={() => setDropdownOpen(o => !o)}
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
            >
              <div className="avatar avatar-sm">{initials}</div>
              <span className="user-dropdown-name">{displayName}</span>
              <span className="dropdown-caret">{dropdownOpen ? '▲' : '▼'}</span>
            </button>
            {dropdownOpen && (
              <div className="user-dropdown-menu">
                <div className="dropdown-header">
                  <div className="dropdown-user-name">{displayName}</div>
                  <div className="dropdown-user-email">{user.email}</div>
                </div>
                <div className="dropdown-divider" />
                <button
                  className="dropdown-item"
                  onClick={() => { setDropdownOpen(false); navigate('/profile'); }}
                >
                  My Profile
                </button>
                <button className="dropdown-item dropdown-item-danger" onClick={handleLogout}>
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
