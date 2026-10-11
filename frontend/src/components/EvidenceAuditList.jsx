import React, { useState } from 'react';
import { ExternalLink, CheckCircle2, XCircle, HelpCircle, FileText, ChevronDown, ChevronUp, Focus } from 'lucide-react';

export default function EvidenceAuditList({ result, onSelectNode, selectedNodeId }) {
  if (!result || !result.sub_claims || result.sub_claims.length === 0) {
    return null;
  }

  const [expandedSubClaims, setExpandedSubClaims] = useState(() => {
    // Expand all by default
    const map = {};
    result.sub_claims.forEach((sc) => {
      map[sc.id] = true;
    });
    return map;
  });

  const toggleSubClaim = (id) => {
    setExpandedSubClaims((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const tierMeta = {
    1: { label: 'T1 Fact-Check / Academic', color: '#eab308', bg: 'rgba(234, 179, 8, 0.12)' },
    2: { label: 'T2 Government / Major News', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)' },
    3: { label: 'T3 Specialist / Regional', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.12)' },
    4: { label: 'T4 Web / General', color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' },
  };

  const evidenceList = result.evidence || [];

  return (
    <div className="glass-panel" style={{ padding: '22px 26px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '800', color: '#f8fafc' }}>
              Sub-Claims & Verbatim Evidence Audit Trail
            </h3>
            <span style={{ fontSize: '11px', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.12)', padding: '2px 8px', borderRadius: '12px', border: '1px solid rgba(56, 189, 248, 0.25)' }}>
              "Cite-Or-It-Didn't-Happen" Audit
            </span>
          </div>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
            Every assertion decomposed and cross-examined against raw extracted source quotes with NLI cross-encoder labels.
          </p>
        </div>

        <button
          onClick={() => {
            const allExpanded = Object.values(expandedSubClaims).every(Boolean);
            const next = {};
            result.sub_claims.forEach((sc) => {
              next[sc.id] = !allExpanded;
            });
            setExpandedSubClaims(next);
          }}
          style={{ fontSize: '12px', color: '#38bdf8', background: 'transparent', textDecoration: 'underline' }}
        >
          {Object.values(expandedSubClaims).every(Boolean) ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {result.sub_claims.map((sc, index) => {
          const isExpanded = !!expandedSubClaims[sc.id];
          const scEvidence = evidenceList.filter((ev) => ev.sub_claim_id === sc.id);

          const isTrue = sc.verdict === 'TRUE';
          const isFalse = sc.verdict === 'FALSE';
          const isPartially = sc.verdict === 'PARTIALLY TRUE';
          const verdictColor = isTrue ? '#10b981' : isFalse ? '#ef4444' : isPartially ? '#f59e0b' : '#94a3b8';
          const verdictBg = isTrue ? 'rgba(16, 185, 129, 0.12)' : isFalse ? 'rgba(239, 68, 68, 0.12)' : isPartially ? 'rgba(245, 158, 11, 0.12)' : 'rgba(148, 163, 184, 0.12)';

          const isSelected = selectedNodeId === sc.id;

          return (
            <div
              key={sc.id}
              style={{
                borderRadius: '10px',
                border: isSelected ? `2px solid ${verdictColor}` : '1px solid #1e293b',
                background: '#0c121e',
                overflow: 'hidden',
                transition: 'border 0.2s ease',
              }}
            >
              {/* Sub-claim Card Header */}
              <div
                onClick={() => toggleSubClaim(sc.id)}
                style={{
                  padding: '14px 18px',
                  background: isExpanded ? 'rgba(15, 23, 42, 0.9)' : 'rgba(15, 23, 42, 0.5)',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px',
                  borderBottom: isExpanded ? '1px solid #1e293b' : 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                  <span style={{ fontSize: '12px', fontWeight: '700', color: '#64748b', minWidth: '22px' }}>
                    #{index + 1}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: '800',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: verdictBg,
                          color: verdictColor,
                          border: `1px solid ${verdictColor}44`,
                        }}
                      >
                        {sc.verdict}
                      </span>
                      <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                        Confidence: {Math.round((sc.confidence || 0) * 100)}% • Score: {sc.score}
                      </span>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>
                        ({scEvidence.length} Evidence Items: {sc.supporting_count || 0} Supports, {sc.refuting_count || 0} Refutes)
                      </span>
                    </div>
                    <p style={{ fontSize: '14px', fontWeight: '600', color: '#f1f5f9', marginTop: '4px' }}>
                      {sc.text}
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {onSelectNode && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectNode({
                          id: sc.id,
                          type: 'subclaim',
                          label: sc.text,
                          fullText: sc.text,
                          verdict: sc.verdict,
                          confidence: sc.confidence,
                          score: sc.score,
                          evidence_count: sc.evidence_count,
                          supporting_count: sc.supporting_count,
                          refuting_count: sc.refuting_count,
                          neutral_count: sc.neutral_count,
                        });
                      }}
                      title="Inspect in Graph"
                      style={{
                        padding: '5px 8px',
                        background: '#1e293b',
                        color: '#38bdf8',
                        borderRadius: '6px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        border: '1px solid #334155',
                      }}
                    >
                      <Focus size={12} />
                      <span>Graph</span>
                    </button>
                  )}
                  {isExpanded ? <ChevronUp size={18} color="#94a3b8" /> : <ChevronDown size={18} color="#94a3b8" />}
                </div>
              </div>

              {/* Sub-claim Evidence Quotes (Visible Directly, Not Hidden Behind Clicks) */}
              {isExpanded && (
                <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {scEvidence.length === 0 ? (
                    <div style={{ color: '#64748b', fontSize: '13px', fontStyle: 'italic', padding: '10px 0' }}>
                      No retrieved evidence met the relevance threshold for this specific assertion.
                    </div>
                  ) : (
                    scEvidence.map((ev) => {
                      const isSupp = ev.nli_label === 'SUPPORTS';
                      const isRef = ev.nli_label === 'REFUTES';
                      const nliColor = isSupp ? '#10b981' : isRef ? '#ef4444' : '#94a3b8';
                      const nliBg = isSupp ? 'rgba(16, 185, 129, 0.12)' : isRef ? 'rgba(239, 68, 68, 0.12)' : 'rgba(148, 163, 184, 0.12)';
                      const tier = tierMeta[ev.domain_tier] || tierMeta[4];
                      const isEvSelected = selectedNodeId === ev.evidence_id;

                      return (
                        <div
                          key={ev.evidence_id}
                          style={{
                            background: isEvSelected ? 'rgba(30, 41, 59, 0.8)' : 'rgba(15, 23, 42, 0.65)',
                            borderRadius: '8px',
                            padding: '12px 16px',
                            border: isEvSelected ? `2px solid #38bdf8` : '1px solid #1e293b',
                            borderLeft: `4px solid ${nliColor}`,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                          }}
                        >
                          {/* Evidence Meta Header */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              {/* NLI Label Badge */}
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  fontSize: '11px',
                                  fontWeight: '800',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  background: nliBg,
                                  color: nliColor,
                                  border: `1px solid ${nliColor}44`,
                                }}
                              >
                                {isSupp && <CheckCircle2 size={12} />}
                                {isRef && <XCircle size={12} />}
                                {!isSupp && !isRef && <HelpCircle size={12} />}
                                <span>{ev.nli_label}</span>
                                <span>({Math.round((ev.nli_confidence || 0) * 100)}%)</span>
                              </span>

                              {/* Source Credibility Tier */}
                              <span
                                style={{
                                  fontSize: '11px',
                                  fontWeight: '700',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  background: tier.bg,
                                  color: tier.color,
                                  border: `1px solid ${tier.color}44`,
                                }}
                              >
                                {tier.label}
                              </span>

                              <span style={{ fontSize: '12px', fontWeight: '600', color: '#cbd5e1' }}>
                                {ev.domain || 'Publisher'}
                              </span>
                            </div>

                            {/* Direct Clickable Source Link */}
                            {ev.source_url && (
                              <a
                                href={ev.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  fontSize: '11px',
                                  color: '#38bdf8',
                                  textDecoration: 'none',
                                  background: '#1e293b',
                                  padding: '3px 8px',
                                  borderRadius: '4px',
                                  border: '1px solid #334155',
                                }}
                              >
                                <span>Visit Source</span>
                                <ExternalLink size={10} />
                              </a>
                            )}
                          </div>

                          {/* Verbatim Extracted Raw Quote */}
                          <div
                            style={{
                              fontSize: '13px',
                              lineHeight: '1.6',
                              color: '#e2e8f0',
                              fontStyle: 'italic',
                              background: '#090d16',
                              padding: '10px 12px',
                              borderRadius: '6px',
                              border: '1px solid #1a2538',
                            }}
                          >
                            "{ev.quote}"
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
