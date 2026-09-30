import { useEffect, useState, useCallback } from 'react';
import { ktService } from '../services/ktService';
import KTDetailModal from '../components/KTDetailModal';
import type { KTListItem } from '../types';
import { KT_STATUS_BADGE, KT_PRIORITY_BADGE, formatDate } from '../utils/kt';
import Icon from '../components/Icon';

type Tab = 'assigned' | 'receiver';

export default function MyKnowledgeTransferPage() {
  const [tab, setTab] = useState<Tab>('assigned');
  const [items, setItems] = useState<KTListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [detailId, setDetailId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await ktService.mine(tab);
      setItems(data);
    } catch {
      setError('Failed to load your knowledge transfer tasks.');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">My Knowledge Transfer</h1>
          <p className="page-subtitle">Handover tasks assigned to you or awaiting your review.</p>
        </div>
      </div>

      <div className="tab-bar" style={{ marginBottom: 16 }}>
        <button className={`tab-btn${tab === 'assigned' ? ' active' : ''}`} onClick={() => setTab('assigned')}>
          Handing Over
        </button>
        <button className={`tab-btn${tab === 'receiver' ? ' active' : ''}`} onClick={() => setTab('receiver')}>
          Receiving
        </button>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card">
        {loading ? (
          <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
        ) : items.length === 0 ? (
          <div className="empty-state" style={{ textAlign: 'center', padding: 32 }}>
            <div className="empty-icon"><Icon name="clipboard" size={40} /></div>
            <h3>Nothing here</h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              {tab === 'assigned' ? 'You have no knowledge transfer tasks to hand over.' : 'No knowledge transfer tasks are awaiting your review.'}
            </p>
          </div>
        ) : (
          <table className="kt-table">
            <thead>
              <tr>
                <th>Project</th><th>Task</th><th>Responsibility</th>
                <th>{tab === 'assigned' ? 'Receiver' : 'From'}</th>
                <th>Priority</th><th>Target Date</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map(kt => (
                <tr key={kt.id}>
                  <td>{kt.project_name || '—'}</td>
                  <td>{kt.title}</td>
                  <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{kt.responsibility || '—'}</td>
                  <td>{tab === 'assigned' ? kt.receiver_name : kt.assigned_to_name}</td>
                  <td><span className={`badge ${KT_PRIORITY_BADGE[kt.priority]}`}>{kt.priority_display}</span></td>
                  <td>{formatDate(kt.target_completion_date)}</td>
                  <td><span className={`badge ${KT_STATUS_BADGE[kt.status]}`}>{kt.status_display}</span></td>
                  <td><button className="btn btn-ghost" onClick={() => setDetailId(kt.id)}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detailId && (
        <KTDetailModal ktId={detailId} onClose={() => setDetailId(null)} onChanged={load} />
      )}
    </div>
  );
}
