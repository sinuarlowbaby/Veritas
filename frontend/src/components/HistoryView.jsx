import React from 'react';
import { VerdictDot, verdictClass, verdictLabel } from './VerdictDot';

/**
 * HistoryView — Minimal rows: dot, claim text, verdict word in serif (right), hairline separators.
 * Clicking a history row replays that job.
 */
export default function HistoryView({ history, onSelect }) {
  if (!history?.length) {
    return (
      <div className="view-container">
        <h2 className="view-title">History</h2>
        <p className="view-subtitle" style={{ marginBottom: 0 }}>
          Your past audits will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="view-container" aria-label="Audit history">
      <h2 className="view-title">History</h2>
      <p className="view-subtitle">
        {history.length} past audit{history.length !== 1 ? 's' : ''}
      </p>

      <div className="history-list" role="list">
        {history.map((item, i) => {
          const cls = verdictClass(item.result?.verdict);
          const label = verdictLabel(item.result?.verdict);
          const claim = item.result?.claim || item.claim || 'Unknown claim';

          return (
            <button
              key={item.job_id || i}
              className="history-row"
              role="listitem"
              onClick={() => onSelect?.(item)}
              aria-label={`Audit: ${claim.slice(0, 60)} — ${label}`}
            >
              <VerdictDot verdict={item.result?.verdict} size={7} />
              <span className="history-claim">
                {claim.length > 90 ? claim.slice(0, 90) + '…' : claim}
              </span>
              <span
                className={`history-verdict-word ${cls}`}
                style={{
                  color: `var(--verdict-${cls})`,
                  fontFamily: "'Lora', Georgia, serif",
                  fontSize: 14,
                  fontWeight: 500,
                }}
              >
                {label.replace('.', '')}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
