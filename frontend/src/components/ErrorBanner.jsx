import React from 'react';
import { AlertCircle, WifiOff, Clock, ServerCrash, X } from 'lucide-react';

/**
 * ErrorBanner — Typed, actionable error display.
 * Accepts a structured error object { message, hint, retryable }
 * or a plain string (backwards-compatible).
 * No dark background, no glow — hairline red border on off-white.
 */
export default function ErrorBanner({ error, onRetry, onDismiss }) {
  // Normalise: accept plain string OR structured object
  const isObj = error && typeof error === 'object';
  const message = isObj ? error.message : (error || 'An unexpected error occurred.');
  const hint    = isObj ? error.hint    : null;
  const retryable = isObj ? error.retryable : true;

  // Pick icon by message content
  const Icon = message.toLowerCase().includes('network') || message.toLowerCase().includes('connection')
    ? WifiOff
    : message.toLowerCase().includes('timed out') || message.toLowerCase().includes('timeout')
    ? Clock
    : message.toLowerCase().includes('unavailable') || message.toLowerCase().includes('internal')
    ? ServerCrash
    : AlertCircle;

  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <Icon size={15} color="#dc2626" strokeWidth={1.8} style={{ flexShrink: 0, marginTop: hint ? 2 : 1 }} />

      <div style={{ flex: 1 }}>
        <p className="error-text">{message}</p>
        {hint && (
          <p style={{ fontSize: 12, color: '#b91c1c', marginTop: 3, lineHeight: 1.4 }}>
            {hint}
          </p>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
        {onRetry && retryable && (
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
