import React from 'react';
import { VerdictDot, verdictClass, verdictLabel } from './VerdictDot';
import { Shield } from 'lucide-react';

/**
 * HistoryView — standalone page view of audit history.
 * Dot + claim text + serif verdict word + date.
 * Clicking a row loads that job (shows evidence in audit view).
 */
export default function HistoryView({ history, onSelect }) {
  if (!history?.length) {
    return (
      <div className="view-container">
        <h2 className="view-title">History</h2>
        <div className="audit-empty-state" style={{ paddingTop: 40 }}>
          <div className="audit-empty-icon">
            <Shield size={20} color="var(--text-muted)" strokeWidth={1.5} />
          </div>
          <p className="audit-empty-title">No audits yet</p>
          <p className="audit-empty-sub">
            Complete your first audit to see it here. Your full history is stored locally.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="view-container" aria-label="Audit history">
      <h2 className="view-title">History</h2>
      <p className="view-subtitle">
        {history.length} past audit{history.length !== 1 ? 's' : ''} · stored locally
      </p>

      <div className="history-list" role="list">
        {history.map((item, i) => {
          const cls = verdictClass(item.result?.verdict);
          const label = verdictLabel(item.result?.verdict).replace('.', '');
          const claim = item.result?.claim || 'Unknown claim';
          const ts = item._timestamp
            ? new Date(item._timestamp).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'short', year: 'numeric',
              })
            : null;
          const evidenceCount = item.result?.evidence?.length ?? 0;
          const latency = item.latency_ms ? `${(item.latency_ms / 1000).toFixed(1)}s` : null;

          return (
            <button
              key={item.job_id || i}
              className="history-row"
              role="listitem"
              onClick={() => onSelect?.(item)}
              aria-label={`${claim.slice(0, 60)} — ${label}`}
              style={{ width: '100%' }}
            >
              {/* Colored dot */}
              <VerdictDot verdict={item.result?.verdict} size={7} />

              {/* Claim + meta */}
              <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                <div className="history-claim">
                  {claim.length > 90 ? claim.slice(0, 90) + '…' : claim}
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  marginTop: 3, fontSize: 11, color: 'var(--text-muted)'
                }}>
                  {ts && <span>{ts}</span>}
                  {ts && latency && <span style={{ color: 'var(--border-mid)' }}>·</span>}
                  {latency && <span>{latency}</span>}
                  {evidenceCount > 0 && (
                    <>
                      <span style={{ color: 'var(--border-mid)' }}>·</span>
                      <span>{evidenceCount} source{evidenceCount !== 1 ? 's' : ''}</span>
                    </>
                  )}
                </div>
              </div>

              {/* Verdict word in serif */}
              <span
                style={{
                  fontFamily: "'Lora', Georgia, serif",
                  fontSize: 14,
                  fontWeight: 500,
                  color: `var(--verdict-${cls})`,
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
