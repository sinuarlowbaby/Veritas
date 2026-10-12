import React from 'react';
import { VerdictDot, nliClass, nliLabel } from './VerdictDot';

/**
 * EvidenceView — Flat list of quote cards, separated by hairlines, newest first.
 * Each item: sub-claim label (small caps), then serif italic quote + evidence meta.
 */
export default function EvidenceView({ result }) {
  if (!result?.evidence?.length) {
    return (
      <div className="view-container">
        <h2 className="view-title">Evidence</h2>
        <p className="view-subtitle" style={{ marginBottom: 0 }}>
          Submit a claim to retrieve evidence.
        </p>
      </div>
    );
  }

  // Newest first (by index reversed since they're added chronologically)
  const items = [...result.evidence].reverse();

  return (
    <div className="view-container" aria-label="Evidence list">
      <h2 className="view-title">Evidence</h2>
      <p className="view-subtitle">
        {items.length} item{items.length !== 1 ? 's' : ''} retrieved — newest first
      </p>

      <div className="evidence-list" role="list">
        {items.map((ev, i) => {
          const cls = nliClass(ev.nli_label);
          const label = nliLabel(ev.nli_label);
          const pct = ev.nli_confidence
            ? `${Math.round(ev.nli_confidence * 100)}%`
            : null;
          const tier = ev.domain_tier ? `T${ev.domain_tier}` : null;
          const domain = ev.domain
            || (() => { try { return new URL(ev.source_url || '').hostname; } catch { return ev.source_url; } })();

          return (
            <article
              key={ev.evidence_id || i}
              className="evidence-list-item"
              role="listitem"
            >
              {/* Sub-claim provenance label */}
              <p className="evidence-list-meta">
                {ev.sub_claim
                  ? ev.sub_claim.length > 80
                    ? ev.sub_claim.slice(0, 80) + '…'
                    : ev.sub_claim
                  : ev.sub_claim_id}
              </p>

              {/* Serif italic quote with left border */}
              <div className="evidence-quote-block">
                <p className="evidence-quote-text">
                  "{ev.quote}"
                </p>
                <div className="evidence-meta-row">
                  <VerdictDot
                    verdict={cls === 'true' ? 'TRUE' : cls === 'false' ? 'FALSE' : 'MIXED'}
                    size={7}
                  />
                  <span style={{ color: `var(--verdict-${cls})` }}>{label}</span>
                  {pct && (
                    <>
                      <span className="evidence-meta-sep">·</span>
                      <span>{pct}</span>
                    </>
                  )}
                  <span className="evidence-meta-sep">—</span>
                  <a
                    href={ev.source_url}
                    className="evidence-source-link"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Source: ${domain}`}
                  >
                    {domain}
                  </a>
                  {tier && (
                    <>
                      <span className="evidence-meta-sep">·</span>
                      <span>{tier}</span>
                    </>
                  )}
                  {ev.retrieved_by && (
                    <>
                      <span className="evidence-meta-sep">·</span>
                      <span style={{ fontStyle: 'italic' }}>{ev.retrieved_by}</span>
                    </>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
