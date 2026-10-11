import React, { useState } from 'react';
import { Search, Sparkles, Loader2, Play, Zap } from 'lucide-react';

export default function ClaimInput({ onVerify, loading, currentStage, elapsedTime }) {
  const [claimText, setClaimText] = useState(
    'Finance Ministry eliminates all income tax for senior citizens over 60 starting April 1'
  );

  const sampleClaims = [
    {
      title: 'Senior Citizen Tax Rumor (Viral False)',
      text: 'Finance Ministry eliminates all income tax for senior citizens over 60 starting April 1',
    },
    {
      title: 'Papaya Leaf Dengue Cure (Medical Claim)',
      text: 'Dengue fever can be completely cured within 48 hours by drinking raw papaya leaf juice extract',
    },
    {
      title: 'James Webb Exoplanet (Scientific Discovery)',
      text: 'NASA James Webb Space Telescope detected carbon-bearing molecules including methane and carbon dioxide on exoplanet K2-18b',
    },
    {
      title: 'Ganymede Crystal City (Abstention Case)',
      text: "Astronomers discover subterranean crystalline city on Jupiter's moon Ganymede",
    },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!claimText.trim() || loading) return;
    onVerify(claimText.trim());
  };

  const stageLabels = {
    queued: 'Queuing pipeline task...',
    decomposing: 'Decomposing claim into atomic sub-assertions...',
    harvesting_evidence: 'Proponent & Skeptic agents harvesting web & curated corpus...',
    sanitizing: 'Lexical alignment & citation sanitization...',
    judge_evaluating: 'NLI cross-encoder matrix & deterministic judge scoring...',
    completed: 'Verification complete!',
  };

  return (
    <div className="glass-panel" style={{ padding: '20px 24px' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} color="#38bdf8" />
            <span>Enter Headline or Claim to Audit:</span>
          </label>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>
            Multi-Agent Debate • Cross-Encoder NLI • Deterministic Judge
          </span>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <textarea
            rows={2}
            value={claimText}
            onChange={(e) => setClaimText(e.target.value)}
            placeholder="Paste any headline, viral social media claim, or news assertion..."
            disabled={loading}
            style={{
              flex: 1,
              background: '#090d16',
              border: '1px solid #334155',
              borderRadius: '10px',
              color: '#f8fafc',
              padding: '12px 16px',
              fontSize: '14px',
              lineHeight: '1.5',
              resize: 'none',
            }}
          />
          <button
            type="submit"
            disabled={loading || !claimText.trim()}
            style={{
              padding: '0 24px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0284c7, #2563eb)',
              color: '#ffffff',
              fontWeight: '700',
              fontSize: '14px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              boxShadow: '0 4px 14px rgba(2, 132, 199, 0.4)',
            }}
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Auditing...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="#ffffff" />
                <span>Verify Claim</span>
              </>
            )}
          </button>
        </div>

        {/* Demo Sample Claim Pills */}
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '600' }}>Demo Presets:</span>
          {sampleClaims.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              disabled={loading}
              onClick={() => setClaimText(sample.text)}
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                background: 'rgba(30, 41, 59, 0.6)',
                color: '#cbd5e1',
                borderRadius: '6px',
                border: '1px solid #1e293b',
                transition: 'all 0.15s',
              }}
            >
              {sample.title}
            </button>
          ))}
        </div>

        {/* Live Progress Indicator during Async Polling */}
        {loading && (
          <div
            style={{
              marginTop: '4px',
              padding: '12px 16px',
              background: 'rgba(15, 23, 42, 0.8)',
              borderRadius: '8px',
              border: '1px solid #1e293b',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Loader2 size={14} color="#38bdf8" className="animate-spin" />
                <span style={{ fontSize: '13px', fontWeight: '600', color: '#38bdf8' }}>
                  {stageLabels[currentStage] || 'Processing verification job...'}
                </span>
              </div>
              <span style={{ fontSize: '12px', color: '#94a3b8', fontFamily: 'monospace' }}>
                +{elapsedTime}s
              </span>
            </div>

            {/* Simulated stage progress bar */}
            <div style={{ width: '100%', height: '4px', background: '#1e293b', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, #38bdf8, #818cf8)',
                  width:
                    currentStage === 'decomposing'
                      ? '25%'
                      : currentStage === 'harvesting_evidence'
                      ? '50%'
                      : currentStage === 'sanitizing'
                      ? '70%'
                      : currentStage === 'judge_evaluating'
                      ? '90%'
                      : '15%',
                  transition: 'width 0.5s ease',
                }}
              />
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
