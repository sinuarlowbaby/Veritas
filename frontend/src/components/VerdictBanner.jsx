import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, HelpCircle, Zap, Clock, Cpu, ExternalLink } from 'lucide-react';

export default function VerdictBanner({ jobData }) {
  if (!jobData || !jobData.result) return null;

  const result = jobData.result;
  const verdict = result.verdict || 'UNVERIFIED';
  const confidencePct = Math.round((result.confidence || 0) * 100);
  const score = result.score;
  const isAbstained = result.is_abstained;
  const isCached = jobData.cached;
  const latencyMs = jobData.latency_ms;
  const tokenCount = jobData.token_count || 0;

  const verdictConfig = {
    TRUE: {
      color: '#10b981',
      bg: 'rgba(16, 185, 129, 0.12)',
      border: '#059669',
      icon: <CheckCircle2 size={24} color="#10b981" />,
      tag: 'VERIFIED TRUE',
    },
    FALSE: {
      color: '#ef4444',
      bg: 'rgba(239, 68, 68, 0.12)',
      border: '#dc2626',
      icon: <XCircle size={24} color="#ef4444" />,
      tag: 'VERIFIED FALSE / DEBUNKED',
    },
    'PARTIALLY TRUE': {
      color: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.12)',
      border: '#d97706',
      icon: <AlertTriangle size={24} color="#f59e0b" />,
      tag: 'PARTIALLY TRUE / MIXED CONTEXT',
    },
    UNVERIFIED: {
      color: '#94a3b8',
      bg: 'rgba(148, 163, 184, 0.12)',
      border: '#64748b',
      icon: <HelpCircle size={24} color="#94a3b8" />,
      tag: isAbstained ? 'ABSTAINED (INSUFFICIENT EVIDENCE)' : 'UNVERIFIED',
    },
  };

  const cfg = verdictConfig[verdict] || verdictConfig['UNVERIFIED'];

  return (
    <div
      className="glass-panel"
      style={{
        padding: '20px 24px',
        border: `1px solid ${cfg.border}`,
        background: `linear-gradient(180deg, ${cfg.bg} 0%, rgba(15, 23, 42, 0.6) 100%)`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '14px', marginBottom: '14px' }}>
        {/* Left: Verdict & Confidence */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {cfg.icon}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '24px', fontWeight: '800', color: cfg.color, letterSpacing: '-0.02em' }}>
                {cfg.tag}
              </h2>
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: '700',
                  padding: '3px 10px',
                  borderRadius: '12px',
                  background: 'rgba(0, 0, 0, 0.4)',
                  color: '#f8fafc',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                }}
              >
                {confidencePct}% Confidence
              </span>
            </div>
            <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '2px' }}>
              Aggregated math score: <code style={{ color: cfg.color }}>{score}</code>
            </p>
          </div>
        </div>

        {/* Right: Telemetry (Cache, Latency, Tokens) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {isCached ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                borderRadius: '8px',
                background: 'rgba(16, 185, 129, 0.2)',
                border: '1px solid #10b981',
                color: '#34d399',
                fontSize: '12px',
                fontWeight: '700',
              }}
            >
              <Zap size={14} />
              <span>Instant Cache Hit ({latencyMs || 1.2}ms)</span>
            </div>
          ) : (
            latencyMs && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '5px 10px',
                  borderRadius: '8px',
                  background: 'rgba(30, 41, 59, 0.7)',
                  border: '1px solid #334155',
                  color: '#94a3b8',
                  fontSize: '12px',
                }}
              >
                <Clock size={13} />
                <span>{Math.round(latencyMs / 100) / 10}s latency</span>
              </div>
            )
          )}

          {tokenCount > 0 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 10px',
                borderRadius: '8px',
                background: 'rgba(30, 41, 59, 0.7)',
                border: '1px solid #334155',
                color: '#94a3b8',
                fontSize: '12px',
              }}
            >
              <Cpu size={13} />
              <span>{tokenCount} tokens</span>
            </div>
          )}

          <div
            style={{
              padding: '5px 10px',
              borderRadius: '8px',
              background: 'rgba(30, 41, 59, 0.7)',
              border: '1px solid #334155',
              color: '#38bdf8',
              fontSize: '11px',
              fontFamily: 'monospace',
            }}
          >
            {jobData.job_id}
          </div>
        </div>
      </div>

      {/* Narrative Explanation */}
      {result.explanation && (
        <div style={{ marginTop: '10px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '12px' }}>
          <h5 style={{ fontSize: '12px', textTransform: 'uppercase', color: '#64748b', fontWeight: '700', marginBottom: '6px' }}>
            Audit Summary & Synthesis
          </h5>
          <p style={{ fontSize: '14px', lineHeight: '1.6', color: '#e2e8f0' }}>
            {result.explanation}
          </p>
        </div>
      )}

      {/* Key Citations */}
      {result.key_citations && result.key_citations.length > 0 && (
        <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>Primary Citations:</span>
          {result.key_citations.map((cite, i) => (
            <a
              key={i}
              href={cite}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: '11px',
                padding: '3px 8px',
                background: 'rgba(15, 23, 42, 0.8)',
                color: '#38bdf8',
                borderRadius: '4px',
                border: '1px solid #334155',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span>{cite.replace(/^https?:\/\/(www\.)?/, '').substring(0, 30)}...</span>
              <ExternalLink size={10} />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
