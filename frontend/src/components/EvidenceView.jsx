import React, { useState } from 'react';
import { VerdictDot, nliClass, nliLabel } from './VerdictDot';
import { FileText, Database, Globe } from 'lucide-react';

const VERDICT_FILTERS = [
  { key: 'all',      label: 'All verdicts' },
  { key: 'refutes',  label: 'Refutes' },
  { key: 'supports', label: 'Supports' },
  { key: 'neutral',  label: 'Neutral' },
];

const SOURCE_FILTERS = [
  { key: 'all', label: 'All sources' },
  { key: 'rag', label: 'Curated RAG' },
  { key: 'web', label: 'Live Web' },
];

function isCuratedRAG(ev) {
  return (
    ev.curated === true ||
    ev.source_type === 'rag' ||
    (typeof ev.source === 'string' && ev.source.startsWith('curated_rag'))
  );
}

function matchesVerdict(ev, filter) {
  if (filter === 'all') return true;
  const label = (ev.nli_label || '').toUpperCase();
  if (filter === 'refutes')  return label === 'REFUTES'  || label === 'REFUTED';
  if (filter === 'supports') return label === 'SUPPORTS' || label === 'SUPPORTED';
  if (filter === 'neutral')  return label === 'NEUTRAL'  || label === 'NEI';
  return true;
}

function matchesSource(ev, filter) {
  if (filter === 'all') return true;
  const rag = isCuratedRAG(ev);
  if (filter === 'rag') return rag;
  if (filter === 'web') return !rag;
  return true;
}

/**
 * EvidenceView — Flat list of quote cards, hairline separators, newest first.
 * Features:
 *  - Prominent visual separation for RAG vs Web data (distinct indigo badge & highlight).
 *  - Verdict filter (All, Refutes, Supports, Neutral).
 *  - Source filter (All sources, Curated RAG, Live Web).
 */
export default function EvidenceView({ result }) {
  const [verdictFilter, setVerdictFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');

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

  // Reverse chronological
  const allItems = [...result.evidence].reverse();

  // Filter items
  const filtered = allItems.filter(
    (ev) => matchesVerdict(ev, verdictFilter) && matchesSource(ev, sourceFilter)
  );

  // Counts for verdict buttons
  const verdictCounts = {
    all:      allItems.length,
    refutes:  allItems.filter((e) => matchesVerdict(e, 'refutes')).length,
    supports: allItems.filter((e) => matchesVerdict(e, 'supports')).length,
    neutral:  allItems.filter((e) => matchesVerdict(e, 'neutral')).length,
  };

  // Counts for source buttons
  const ragCount = allItems.filter(isCuratedRAG).length;
  const webCount = allItems.length - ragCount;

  return (
    <div className="view-container" aria-label="Evidence list">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
        <h2 className="view-title" style={{ marginBottom: 0 }}>Evidence</h2>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {ragCount} RAG · {webCount} Web
        </span>
      </div>

      <p className="view-subtitle">
        {allItems.length} total source items retrieved — verified by NLI cross-encoder
      </p>

      {/* ── Filters Container ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 24 }}>
        {/* Row 1: Verdict filters */}
        <div
          role="group"
          aria-label="Filter evidence by verdict type"
          style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}
        >
          {VERDICT_FILTERS.map(({ key, label }) => {
            const isActive = verdictFilter === key;
            const count = verdictCounts[key];
            return (
              <button
                key={key}
                id={`evidence-filter-${key}`}
                onClick={() => setVerdictFilter(key)}
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
                {key !== 'all' && (
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background:
                        key === 'refutes'
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

        {/* Row 2: Source filters (RAG vs Web) */}
        <div
          role="group"
          aria-label="Filter evidence by source type"
          style={{ display: 'flex', gap: 6, alignItems: 'center' }}
        >
          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 4 }}>Source:</span>
          {SOURCE_FILTERS.map(({ key, label }) => {
            const isActive = sourceFilter === key;
            const count = key === 'all' ? allItems.length : key === 'rag' ? ragCount : webCount;
            return (
              <button
                key={key}
                id={`source-filter-${key}`}
                onClick={() => setSourceFilter(key)}
                aria-pressed={isActive}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  padding: '3px 10px',
                  fontSize: 11,
                  fontWeight: isActive ? 500 : 400,
                  color: isActive
                    ? key === 'rag'
                      ? 'var(--rag-color)'
                      : 'var(--text-primary)'
                    : 'var(--text-muted)',
                  border: `1px solid ${
                    isActive
                      ? key === 'rag'
                        ? 'var(--rag-border)'
                        : 'var(--border-mid)'
                      : 'var(--border)'
                  }`,
                  borderRadius: 6,
                  background: isActive
                    ? key === 'rag'
                      ? 'var(--rag-bg)'
                      : 'var(--bg-off)'
                    : 'var(--white)',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {key === 'rag' && <Database size={11} strokeWidth={2} />}
                {key === 'web' && <Globe size={11} strokeWidth={1.8} />}
                {label} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Evidence list ── */}
      {filtered.length === 0 ? (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic', paddingTop: 8 }}>
          No evidence items match the selected filters.
        </p>
      ) : (
        <div className="evidence-list" role="list">
          {filtered.map((ev, i) => {
            const cls = nliClass(ev.nli_label);
            const label = nliLabel(ev.nli_label);
            const isRag = isCuratedRAG(ev);
            const pct = ev.nli_confidence ? `${Math.round(ev.nli_confidence * 100)}%` : null;
            const tier = ev.domain_tier ? `T${ev.domain_tier}` : null;
            let domain = ev.domain;
            if (!domain && ev.source_url) {
              try {
                domain = new URL(ev.source_url).hostname;
              } catch {
                domain = ev.source_url;
              }
            }

            return (
              <article key={ev.evidence_id || i} className="evidence-list-item" role="listitem">
                {/* Sub-claim provenance label + Source badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <p className="evidence-list-meta" style={{ marginBottom: 0 }}>
                    {ev.sub_claim
                      ? ev.sub_claim.length > 70
                        ? ev.sub_claim.slice(0, 70) + '…'
                        : ev.sub_claim
                      : ev.sub_claim_id}
                  </p>

                  {/* Distinct RAG vs Web Badge */}
                  {isRag ? (
                    <span
                      className="source-badge rag"
                      title="Ground-truth fact-check retrieved from vector database"
                      aria-label="Curated RAG ground truth"
                    >
                      <span className="rag-badge-dot" />
                      Curated RAG
                    </span>
                  ) : (
                    <span
                      className="source-badge web"
                      title="Real-time web search result"
                      aria-label="Live web search result"
                    >
                      Live Web
                    </span>
                  )}
                </div>

                {/* Quote block — with distinct RAG left border accent when isRag */}
                <div className={`evidence-quote-block ${isRag ? 'rag-quote' : ''}`}>
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
