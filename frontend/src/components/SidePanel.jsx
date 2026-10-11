import React from 'react';
import { ExternalLink, ShieldCheck, AlertCircle, HelpCircle, CheckCircle2, XCircle, Info, Bookmark, FileText } from 'lucide-react';

export default function SidePanel({ selectedNode, overallResult }) {
  if (!selectedNode) {
    return (
      <div className="glass-panel" style={{ padding: '24px', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', color: '#64748b' }}>
        <Info size={36} color="#475569" style={{ marginBottom: '12px' }} />
        <h4 style={{ color: '#94a3b8', fontSize: '15px', marginBottom: '6px' }}>Node Audit Inspector</h4>
        <p style={{ fontSize: '13px', lineHeight: '1.5', maxWidth: '260px' }}>
          Click on any node in the provenance graph above to inspect verbatim evidence quotes, publisher credibility tiers, and calibrated NLI confidence scores.
        </p>
      </div>
    );
  }

  // Case 1: Evidence Node Selected
  if (selectedNode.type === 'evidence') {
    const isSupports = selectedNode.nli_label === 'SUPPORTS';
    const isRefutes = selectedNode.nli_label === 'REFUTES';
    const nliColor = isSupports ? '#10b981' : isRefutes ? '#ef4444' : '#94a3b8';
    const nliBg = isSupports ? 'rgba(16, 185, 129, 0.15)' : isRefutes ? 'rgba(239, 68, 68, 0.15)' : 'rgba(148, 163, 184, 0.15)';
    const tier = selectedNode.domain_tier || 4;
    const tierLabels = {
      1: { name: 'Tier 1: Official / Fact-Checker', color: '#eab308' },
      2: { name: 'Tier 2: Government / Major Media', color: '#38bdf8' },
      3: { name: 'Tier 3: Specialist / Regional', color: '#c084fc' },
      4: { name: 'Tier 4: General Web', color: '#94a3b8' },
    };
    const tierInfo = tierLabels[tier] || tierLabels[4];

    return (
      <div className="glass-panel" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
        {/* Header / Publisher Domain */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b', fontWeight: '600' }}>
              Evidence Item
            </span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: '600',
                padding: '2px 8px',
                borderRadius: '4px',
                background: `${tierInfo.color}22`,
                color: tierInfo.color,
                border: `1px solid ${tierInfo.color}44`,
              }}
            >
              {tierInfo.name}
            </span>
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#f8fafc', wordBreak: 'break-all' }}>
            {selectedNode.domain || 'Source Document'}
          </h3>
        </div>

        {/* NLI Label & Confidence Bar */}
        <div style={{ background: nliBg, border: `1px solid ${nliColor}44`, borderRadius: '10px', padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {isSupports && <CheckCircle2 size={16} color={nliColor} />}
              {isRefutes && <XCircle size={16} color={nliColor} />}
              {!isSupports && !isRefutes && <HelpCircle size={16} color={nliColor} />}
              <span style={{ fontSize: '14px', fontWeight: '700', color: nliColor }}>
                {selectedNode.nli_label}
              </span>
            </div>
            <span style={{ fontSize: '13px', fontWeight: '600', color: '#cbd5e1' }}>
              {Math.round((selectedNode.nli_confidence || 0) * 100)}% Confidence
            </span>
          </div>
          {/* Visual Confidence Bar */}
          <div style={{ width: '100%', height: '6px', background: 'rgba(0,0,0,0.4)', borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.round((selectedNode.nli_confidence || 0) * 100)}%`,
                height: '100%',
                background: nliColor,
                borderRadius: '3px',
              }}
            />
          </div>
        </div>

        {/* Verbatim Quote Display */}
        <div>
          <label style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '8px' }}>
            <FileText size={14} /> Verbatim Extracted Quote:
          </label>
          <div
            style={{
              padding: '14px',
              borderRadius: '8px',
              background: 'rgba(15, 23, 42, 0.9)',
              borderLeft: `4px solid ${nliColor}`,
              border: `1px solid #1e293b`,
              borderLeftWidth: '4px',
              fontSize: '13px',
              lineHeight: '1.6',
              color: '#e2e8f0',
              fontStyle: 'italic',
            }}
          >
            "{selectedNode.quote}"
          </div>
        </div>

        {/* Evaluated Sub-claim Context */}
        {selectedNode.sub_claim && (
          <div>
            <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600', textTransform: 'uppercase' }}>
              Associated Sub-Claim
            </span>
            <p style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px', lineHeight: '1.4' }}>
              {selectedNode.sub_claim}
            </p>
          </div>
        )}

        {/* Source URL & External Link Button */}
        {selectedNode.source_url && (
          <div style={{ marginTop: 'auto', paddingTop: '8px' }}>
            <a
              href={selectedNode.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                width: '100%',
                padding: '10px 14px',
                background: '#1e293b',
                color: '#38bdf8',
                fontSize: '13px',
                fontWeight: '600',
                borderRadius: '8px',
                textDecoration: 'none',
                border: '1px solid #334155',
                transition: 'background 0.2s',
              }}
            >
              <span>Visit Source URL</span>
              <ExternalLink size={14} />
            </a>
          </div>
        )}
      </div>
    );
  }

  // Case 2: Sub-claim Node Selected
  if (selectedNode.type === 'subclaim') {
    const isTrue = selectedNode.verdict === 'TRUE';
    const isFalse = selectedNode.verdict === 'FALSE';
    const verdictColor = isTrue ? '#10b981' : isFalse ? '#ef4444' : '#f59e0b';

    return (
      <div className="glass-panel" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
        <div>
          <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: '600' }}>
            Sub-Claim Breakdown
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: '700', padding: '3px 10px', borderRadius: '4px', background: `${verdictColor}22`, color: verdictColor, border: `1px solid ${verdictColor}` }}>
              {selectedNode.verdict}
            </span>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              Confidence: {Math.round((selectedNode.confidence || 0) * 100)}%
            </span>
          </div>
        </div>

        <div>
          <label style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8' }}>Decomposed Assertion:</label>
          <p style={{ fontSize: '14px', color: '#f1f5f9', marginTop: '4px', lineHeight: '1.5', background: 'rgba(15, 23, 42, 0.6)', padding: '10px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            {selectedNode.fullText || selectedNode.label}
          </p>
        </div>

        {/* Evidence Balance */}
        <div style={{ background: '#0f172a', padding: '12px', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <span style={{ fontSize: '12px', fontWeight: '600', color: '#cbd5e1', display: 'block', marginBottom: '8px' }}>
            Evidence Distribution ({selectedNode.evidence_count} Total)
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', textAlign: 'center' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '6px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              <span style={{ display: 'block', fontSize: '16px', fontWeight: '700', color: '#10b981' }}>{selectedNode.supporting_count || 0}</span>
              <span style={{ fontSize: '10px', color: '#94a3b8' }}>Supports</span>
            </div>
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '6px', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              <span style={{ display: 'block', fontSize: '16px', fontWeight: '700', color: '#ef4444' }}>{selectedNode.refuting_count || 0}</span>
              <span style={{ fontSize: '10px', color: '#94a3b8' }}>Refutes</span>
            </div>
            <div style={{ background: 'rgba(100, 116, 139, 0.1)', padding: '6px', borderRadius: '6px', border: '1px solid rgba(100, 116, 139, 0.3)' }}>
              <span style={{ display: 'block', fontSize: '16px', fontWeight: '700', color: '#94a3b8' }}>{selectedNode.neutral_count || 0}</span>
              <span style={{ fontSize: '10px', color: '#64748b' }}>Neutral</span>
            </div>
          </div>
        </div>

        {selectedNode.score !== undefined && (
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>
            Deterministic Math Score: <code style={{ color: '#38bdf8' }}>{selectedNode.score}</code>
          </div>
        )}
      </div>
    );
  }

  // Case 3: Root Verdict Node Selected
  if (selectedNode.type === 'verdict') {
    return (
      <div className="glass-panel" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>
        <div>
          <span style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: '600' }}>
            Root Claim Verdict
          </span>
          <h3 style={{ fontSize: '20px', fontWeight: '800', color: selectedNode.verdict === 'TRUE' ? '#10b981' : selectedNode.verdict === 'FALSE' ? '#ef4444' : '#f59e0b', marginTop: '4px' }}>
            {selectedNode.verdict}
          </h3>
        </div>

        <div>
          <label style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8' }}>Narrative Explanation:</label>
          <p style={{ fontSize: '13px', lineHeight: '1.6', color: '#cbd5e1', marginTop: '4px' }}>
            {selectedNode.explanation || overallResult?.explanation}
          </p>
        </div>

        {selectedNode.key_citations && selectedNode.key_citations.length > 0 && (
          <div>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8', display: 'block', marginBottom: '6px' }}>
              Key Citations:
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {selectedNode.key_citations.map((cite, i) => (
                <a
                  key={i}
                  href={cite}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: '12px', color: '#38bdf8', textDecoration: 'none', wordBreak: 'break-all' }}
                >
                  🔗 {cite}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}
