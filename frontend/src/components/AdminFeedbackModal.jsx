import React, { useState, useEffect } from 'react';
import { X, RefreshCw, ThumbsDown, ThumbsUp, AlertCircle, Clock } from 'lucide-react';

export default function AdminFeedbackModal({ isOpen, onClose }) {
  const [filterRating, setFilterRating] = useState('thumbs_down'); // default to flagged reviews
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchFeedback = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = filterRating ? `/api/feedback?rating=${filterRating}` : '/api/feedback';
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(data.items || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch feedback.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchFeedback();
    }
  }, [isOpen, filterRating]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px',
      }}
    >
      <div
        className="glass-panel-glow"
        style={{
          width: '100%',
          maxWidth: '750px',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: '16px',
          overflow: 'hidden',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#f8fafc' }}>
              Feedback & Flagged Claims Audit View
            </h3>
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>
              Review user-flagged verification errors for benchmark dataset & regression testing.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', color: '#94a3b8', padding: '6px', borderRadius: '6px' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Filter Toolbar */}
        <div
          style={{
            padding: '12px 24px',
            background: 'rgba(15, 23, 42, 0.6)',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setFilterRating('thumbs_down')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: '600',
                borderRadius: '6px',
                background: filterRating === 'thumbs_down' ? '#991b1b' : '#1e293b',
                color: filterRating === 'thumbs_down' ? '#ffffff' : '#94a3b8',
                border: filterRating === 'thumbs_down' ? '1px solid #ef4444' : '1px solid #334155',
              }}
            >
              <ThumbsDown size={14} />
              <span>Flagged Disputed Only</span>
            </button>
            <button
              onClick={() => setFilterRating('')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: '600',
                borderRadius: '6px',
                background: filterRating === '' ? '#334155' : '#1e293b',
                color: filterRating === '' ? '#ffffff' : '#94a3b8',
                border: '1px solid #334155',
              }}
            >
              <span>All Submissions</span>
            </button>
          </div>

          <button
            onClick={fetchFeedback}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              fontSize: '12px',
              background: '#1e293b',
              color: '#38bdf8',
              borderRadius: '6px',
              border: '1px solid #334155',
            }}
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Feedback List */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
              Loading feedback entries...
            </div>
          )}

          {error && (
            <div style={{ color: '#ef4444', textAlign: 'center', padding: '20px' }}>
              Error: {error}
            </div>
          )}

          {!loading && items.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
              <AlertCircle size={32} style={{ margin: '0 auto 10px', display: 'block' }} />
              <p>No feedback records match the current filter.</p>
            </div>
          )}

          {!loading &&
            items.map((fb) => (
              <div
                key={fb.id}
                style={{
                  background: 'rgba(30, 41, 59, 0.4)',
                  border: fb.rating === 'thumbs_down' ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid #334155',
                  borderRadius: '10px',
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {fb.rating === 'thumbs_down' ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '700', color: '#f87171', background: '#7f1d1d', padding: '2px 8px', borderRadius: '4px' }}>
                        <ThumbsDown size={12} /> FLAG
                      </span>
                    ) : (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '700', color: '#34d399', background: '#064e3b', padding: '2px 8px', borderRadius: '4px' }}>
                        <ThumbsUp size={12} /> ACCURATE
                      </span>
                    )}
                    <span style={{ fontSize: '12px', fontWeight: '600', color: '#cbd5e1' }}>
                      Job: <code style={{ color: '#38bdf8' }}>{fb.job_id}</code>
                    </span>
                    {fb.verdict && (
                      <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                        (Verdict: {fb.verdict})
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#64748b' }}>
                    <Clock size={12} />
                    <span>{new Date(fb.created_at).toLocaleString()}</span>
                  </div>
                </div>

                {fb.comment && (
                  <p style={{ fontSize: '13px', color: '#e2e8f0', background: '#0f172a', padding: '10px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                    "{fb.comment}"
                  </p>
                )}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
