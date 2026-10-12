import React, { useState } from 'react';
import { VerdictDot, nliClass, nliLabel } from './VerdictDot';
import { FileText } from 'lucide-react';

const FILTER_OPTIONS = [
  { key: 'all',      label: 'All' },
  { key: 'refutes',  label: 'Refutes' },
  { key: 'supports', label: 'Supports' },
  { key: 'neutral',  label: 'Neutral' },
];

/**
 * Maps a filter key to an nli_label substring match.
 */
function matchesFilter(ev, filter) {
  if (filter === 'all') return true;
  const label = (ev.nli_label || '').toUpperCase();
  if (filter === 'refutes')  return label === 'REFUTES'  || label === 'REFUTED';
  if (filter === 'supports') return label === 'SUPPORTS' || label === 'SUPPORTED';
  if (filter === 'neutral')  return label === 'NEUTRAL'  || label === 'NEI';
  return true;
}

/**
 * EvidenceView — Flat list of quote cards, hairline separators, newest first.
 * Has filter bar: All / Refutes / Supports / Neutral — ghost buttons, no pills.
 */
export default function EvidenceView({ result }) {
  const [filter, setFilter] = useState('all');

  if (!result?.evidence?.length) {
    return (
      <div className="view-container">
        <h2 className="view-title">Evidence</h2>
        <div className="audit-empty-state" style={{ paddingTop: 32 }}>
          <div className="audit-empty-icon">
            <FileText size={18} color="var(--text-muted)" strokeWidth={1.5} />
          </div>
          <p className="audit-empty-title">No evidence retrieved</p>
          <p className="audit-empty-sub">
            Submit a claim first. Evidence will appear here after the pipeline runs.
          </p>
        </div>
      </div>
    );
  }

  // Newest first (reverse chronological)
  const allItems = [...result.evidence].reverse();
  const filtered = allItems.filter((ev) => matchesFilter(ev, filter));

  // Count per type for filter labels
  const counts = {
    all:      allItems.length,
    refutes:  allItems.filter((e) => matchesFilter(e, 'refutes')).length,
    supports: allItems.filter((e) => matchesFilter(e, 'supports')).length,
    neutral:  allItems.filter((e) => matchesFilter(e, 'neutral')).length,
  };

  return (
    <div className="view-container" aria-label="Evidence list">
      <h2 className="view-title">Evidence</h2>
      <p className="view-subtitle">
        {allItems.length} item{allItems.length !== 1 ? 's' : ''} retrieved — newest first
      </p>

      {/* ── Filter bar ── ghost buttons, no pills, no colored backgrounds ── */}
      <div
        role="group"
        aria-label="Filter evidence by verdict type"
        style={{ display: 'flex', gap: 6, marginBottom: 22 }}
      >
        {FILTER_OPTIONS.map(({ key, label }) => {
          const isActive = filter === key;
          const count = counts[key];
          return (
            <button
              key={key}
              id={`evidence-filter-${key}`}
              onClick={() => setFilter(key)}
              aria-pressed={isActive}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 12px',
                fontSize: 12,
                fontWeight: isActive ? 500 : 400,
                color: isActive ? 'var(--teal)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--teal)' : 'var(--border)'}`,
                borderRadius: 100,
                background: isActive ? 'var(--teal-light)' : 'var(--white)',
                transition: 'all 0.15s',
                cursor: 'pointer',
              }}
            >
              {/* Dot for non-"All" filters */}
              {key !== 'all' && (
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: key === 'refutes'
                      ? 'var(--dot-false)'
                      : key === 'supports'
                      ? 'var(--dot-true)'
                      : 'var(--dot-unverified)',
                    flexShrink: 0,
                  }}
                />
              )}
              {label}
              {count > 0 && (
                <span style={{ color: isActive ? 'var(--teal)' : 'var(--text-faint)', fontSize: 11 }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Evidence list ── */}
      {filtered.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic', paddingTop: 8 }}>
          No {filter} evidence for this claim.
        </p>
      ) : (
        <div className="evidence-list" role="list">
          {filtered.map((ev, i) => {
            const cls   = nliClass(ev.nli_label);
            const label = nliLabel(ev.nli_label);
            const pct   = ev.nli_confidence
              ? `${Math.round(ev.nli_confidence * 100)}%`
              : null;
            const tier = ev.domain_tier ? `T${ev.domain_tier}` : null;
            let domain = ev.domain;
            if (!domain && ev.source_url) {
              try { domain = new URL(ev.source_url).hostname; } catch { domain = ev.source_url; }
            }

            return (
              <article key={ev.evidence_id || i} className="evidence-list-item" role="listitem">
                {/* Sub-claim provenance label */}
                <p className="evidence-list-meta">
                  {ev.sub_claim
                    ? ev.sub_claim.length > 80
                      ? ev.sub_claim.slice(0, 80) + '…'
                      : ev.sub_claim
                    : ev.sub_claim_id}
                </p>

                {/* Serif italic quote + left border */}
                <div className="evidence-quote-block">
                  <p className="evidence-quote-text">"{ev.quote}"</p>
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
                      {domain || '—'}
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
      )}
    </div>
  );
}
