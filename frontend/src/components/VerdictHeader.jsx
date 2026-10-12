import React, { useState } from 'react';
import { ChevronRight, RotateCcw } from 'lucide-react';
import { VerdictDot, verdictClass, verdictLabel, nliClass, nliLabel } from './VerdictDot';

/**
 * EvidenceQuote — Serif italic block quote with left border.
 * DOTS ONLY — never pills, never background blocks.
 */
function EvidenceQuote({ evidence }) {
  const cls = nliClass(evidence.nli_label);
  const label = nliLabel(evidence.nli_label);
  const pct = evidence.nli_confidence
    ? `${Math.round(evidence.nli_confidence * 100)}%`
    : null;
  const tier = evidence.domain_tier ? `T${evidence.domain_tier}` : null;

  // Safe domain extraction
  let domain = evidence.domain;
  if (!domain && evidence.source_url) {
    try { domain = new URL(evidence.source_url).hostname; } catch { domain = evidence.source_url; }
  }

  return (
    <div className="evidence-quote-block">
      <p className="evidence-quote-text">
        "{evidence.quote}"
      </p>
      <div className="evidence-meta-row">
        <VerdictDot verdict={cls === 'true' ? 'TRUE' : cls === 'false' ? 'FALSE' : 'MIXED'} size={7} />
        <span style={{ color: `var(--verdict-${cls})` }}>{label}</span>
        {pct && (
          <>
            <span className="evidence-meta-sep">·</span>
            <span>{pct}</span>
          </>
        )}
        <span className="evidence-meta-sep">—</span>
        <a
          href={evidence.source_url}
          className="evidence-source-link"
          target="_blank"
          rel="noopener noreferrer"
        >
          {domain || '—'}
        </a>
        {tier && (
          <>
            <span className="evidence-meta-sep">·</span>
            <span>{tier}</span>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * SubClaimAccordion — dot + text + evidence count + chevron arrow.
 * Expanded: shows matching evidence as serif italic quotes.
 */
function SubClaimAccordion({ subClaim, evidence, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const matchingEvidence = evidence?.filter((e) => e.sub_claim_id === subClaim.id) || [];

  return (
    <div className="accordion-row">
      <button
        className="accordion-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        id={`accordion-${subClaim.id}`}
      >
        <VerdictDot verdict={subClaim.verdict} size={8} />
        <span className="accordion-text">{subClaim.text}</span>
        {subClaim.evidence_count != null && (
          <span className="accordion-count">
            {subClaim.evidence_count} source{subClaim.evidence_count !== 1 ? 's' : ''}
          </span>
        )}
        <ChevronRight
          size={15}
          strokeWidth={1.8}
          className={`accordion-arrow ${open ? 'open' : ''}`}
        />
      </button>

      <div
        className={`accordion-body ${open ? 'open' : ''}`}
        role="region"
        aria-labelledby={`accordion-${subClaim.id}`}
      >
        <div className="accordion-body-inner">
          {matchingEvidence.length > 0 ? (
            matchingEvidence.map((ev) => (
              <EvidenceQuote key={ev.evidence_id} evidence={ev} />
            ))
          ) : (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              No evidence items retrieved for this sub-claim.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * VerdictHeader — Large serif verdict word + metadata row + summary paragraph.
 *
 * Props:
 *   jobData   — full job object from API / history
 *   onReaudit — optional callback; when provided, shows the Re-audit button.
 *               Called with the claim text string.
 */
export default function VerdictHeader({ jobData, onReaudit }) {
  if (!jobData?.result) return null;

  const { result, latency_ms, token_count, cached } = jobData;
  const { verdict, confidence, score, explanation, sub_claims, evidence, claim } = result;

  const cls = verdictClass(verdict);
  const label = verdictLabel(verdict);
  const confPct = confidence != null ? `${Math.round(confidence * 100)}%` : null;
  const latSec  = latency_ms   != null ? `${(latency_ms / 1000).toFixed(1)}s` : null;

  return (
    <section className="verdict-section" aria-label="Audit result">

      {/* ── Verdict word + metadata ── */}
      <div className="verdict-headline-row">
        <h2 className={`verdict-word serif ${cls}`}>
          {label}
        </h2>

        <div className="verdict-meta">
          {confPct && (
            <>
              <span>confidence {confPct}</span>
              <span className="verdict-meta-sep" aria-hidden="true" />
            </>
          )}
          {score != null && (
            <>
              <span>score {score > 0 ? '+' : ''}{score.toFixed(3)}</span>
              <span className="verdict-meta-sep" aria-hidden="true" />
            </>
          )}
          {latSec && (
            <>
              <span>{latSec}</span>
              <span className="verdict-meta-sep" aria-hidden="true" />
            </>
          )}
          {token_count && (
            <>
              <span>{token_count} tokens</span>
              <span className="verdict-meta-sep" aria-hidden="true" />
            </>
          )}

          {/* ── Cached indicator — shown only when cached === true ── */}
          {cached === true && (
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                border: '1px solid var(--border-mid)',
                borderRadius: 4,
                padding: '1px 6px',
                letterSpacing: '0.03em',
              }}
              title="This result was served from the pipeline cache"
              aria-label="Cached result"
            >
              cached
            </span>
          )}
        </div>

        {/* ── Re-audit button — only shown when callback provided ── */}
        {onReaudit && claim && (
          <button
            id="reaudit-btn"
            onClick={() => onReaudit(claim)}
            aria-label="Re-run audit for this claim"
            title="Re-run the pipeline with fresh retrieval"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 12,
              color: 'var(--teal)',
              border: '1px solid var(--teal)',
              borderRadius: 6,
              padding: '4px 10px',
              marginLeft: 'auto',
              background: 'none',
              transition: 'background 0.15s, transform 0.15s',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--teal-light)';
              e.currentTarget.style.transform = 'scale(1.03)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'none';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <RotateCcw size={12} strokeWidth={2} />
            Re-audit
          </button>
        )}
      </div>

      <div className="verdict-divider" role="separator" />

      {/* ── Plain-language summary ── */}
      {explanation && (
        <p className="verdict-summary">{explanation}</p>
      )}

      {/* ── Sub-claims accordion ── */}
      {sub_claims?.length > 0 && (
        <div className="subclaims-section">
          <p className="section-label">Sub-claims · {sub_claims.length}</p>
          {sub_claims.map((sc, i) => (
            <SubClaimAccordion
              key={sc.id}
              subClaim={sc}
              evidence={evidence}
              defaultOpen={i === 0}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export { EvidenceQuote };
