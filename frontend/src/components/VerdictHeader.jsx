import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { VerdictDot, verdictClass, verdictLabel, nliClass, nliLabel } from './VerdictDot';

/**
 * EvidenceQuote — Serif italic block quote with left border.
 * Shows: quote text, then: colored dot + NLI label + confidence + domain + tier
 * DOTS ONLY — never pills, never background blocks.
 */
function EvidenceQuote({ evidence }) {
  const cls = nliClass(evidence.nli_label);
  const label = nliLabel(evidence.nli_label);
  const pct = evidence.nli_confidence
    ? `${Math.round(evidence.nli_confidence * 100)}%`
    : null;
  const tier = evidence.domain_tier ? `T${evidence.domain_tier}` : null;

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
          {evidence.domain || new URL(evidence.source_url || 'https://unknown').hostname}
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
 * SubClaimAccordion row — dot + text + count + chevron.
 * Expanded: shows evidence as serif italic quotes.
 */
function SubClaimAccordion({ subClaim, evidence, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const cls = verdictClass(subClaim.verdict);
  const matchingEvidence = evidence?.filter(
    (e) => e.sub_claim_id === subClaim.id
  ) || [];

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
 * VerdictHeader — Large serif verdict word + muted metadata + summary paragraph.
 * Then sub-claims as accordion rows.
 */
export default function VerdictHeader({ jobData }) {
  if (!jobData?.result) return null;

  const { result, job_id, latency_ms, token_count } = jobData;
  const { verdict, confidence, score, explanation, sub_claims, evidence } = result;

  const cls = verdictClass(verdict);
  const label = verdictLabel(verdict);
  const confPct = confidence ? `${Math.round(confidence * 100)}%` : null;
  const latSec = latency_ms ? `${(latency_ms / 1000).toFixed(1)}s` : null;

  return (
    <section className="verdict-section" aria-label="Audit result">
      {/* Verdict word + metadata on same line */}
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
          {token_count && <span>{token_count} tokens</span>}
        </div>
      </div>

      <div className="verdict-divider" role="separator" />

      {/* Plain-language summary */}
      {explanation && (
        <p className="verdict-summary">{explanation}</p>
      )}

      {/* Sub-claims accordion */}
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
