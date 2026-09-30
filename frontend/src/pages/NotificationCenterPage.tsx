import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationService } from '../services/notificationService';
import type { NotificationItem } from '../types';
import { formatDateTime } from '../utils/kt';
import Icon from '../components/Icon';

export default function NotificationCenterPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'all' | 'unread'>('all');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      setItems(await notificationService.list(tab === 'unread'));
    } catch {
      setError('Failed to load notifications.');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  async function open(n: NotificationItem) {
    if (!n.is_read) { try { await notificationService.markRead(n.id); } catch { /* ignore */ } }
    if (n.related_offboarding) navigate(`/offboarding/${n.related_offboarding}`);
    else load();
  }

  async function markAll() {
    try { await notificationService.markAllRead(); await load(); } catch { /* ignore */ }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">Your offboarding alerts and updates.</p>
        </div>
        <button className="btn btn-secondary" onClick={markAll}>Mark all read</button>
      </div>

      <div className="tab-bar" style={{ marginBottom: 16 }}>
        <button className={`tab-btn${tab === 'all' ? ' active' : ''}`} onClick={() => setTab('all')}>All</button>
        <button className={`tab-btn${tab === 'unread' ? ' active' : ''}`} onClick={() => setTab('unread')}>Unread</button>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
        ) : items.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="bell" size={40} /></div><h3>No notifications</h3>
            <p style={{ color: 'var(--text-secondary)' }}>{tab === 'unread' ? 'You are all caught up.' : 'Nothing here yet.'}</p>
          </div>
        ) : (
          items.map(n => (
            <div key={n.id} className={`notif-row${n.is_read ? '' : ' unread'}`}>
              <div style={{ display: 'flex', gap: 10 }}>
                {!n.is_read && <span className="notif-dot" />}
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{n.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{n.message}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    {n.type_display} · {formatDateTime(n.created_at)}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                {n.related_offboarding && (
                  <button className="btn btn-ghost" onClick={() => open(n)}>Open</button>
                )}
                {!n.is_read && !n.related_offboarding && (
                  <button className="btn btn-ghost" onClick={() => open(n)}>Mark read</button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
