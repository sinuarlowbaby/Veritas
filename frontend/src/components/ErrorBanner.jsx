import React from 'react';
import { AlertOctagon, RotateCcw, XCircle } from 'lucide-react';

export default function ErrorBanner({ error, onRetry, onDismiss }) {
  if (!error) return null;

  return (
    <div
      className="glass-panel"
      style={{
        padding: '16px 20px',
        border: '1px solid #ef4444',
        background: 'rgba(239, 68, 68, 0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        borderRadius: '10px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <AlertOctagon size={24} color="#ef4444" />
        <div>
          <h4 style={{ fontSize: '14px', fontWeight: '700', color: '#f87171' }}>
            Verification Pipeline Notice
          </h4>
          <p style={{ fontSize: '13px', color: '#cbd5e1', marginTop: '2px' }}>
            {error}
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              background: '#dc2626',
              color: '#ffffff',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: '600',
            }}
          >
            <RotateCcw size={13} />
            <span>Retry</span>
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            style={{
              padding: '6px 12px',
              background: 'transparent',
              color: '#94a3b8',
              fontSize: '12px',
            }}
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
