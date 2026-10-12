import React from 'react';
import { AlertCircle, X } from 'lucide-react';

/**
 * ErrorBanner — Subtle error notice.
 * No dark background, no glow — just a hairline red border on off-white.
 */
export default function ErrorBanner({ error, onRetry, onDismiss }) {
  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <AlertCircle size={15} color="#dc2626" strokeWidth={1.8} style={{ flexShrink: 0, marginTop: 1 }} />
      <p className="error-text">{error}</p>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {onRetry && (
          <button
            className="error-retry-btn"
            onClick={onRetry}
            aria-label="Retry verification"
          >
            Retry
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            aria-label="Dismiss error"
            style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
          >
            <X size={15} strokeWidth={1.8} />
          </button>
        )}
      </div>
    </div>
  );
}
