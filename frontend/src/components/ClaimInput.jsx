import React, { useState, useRef } from 'react';
import { RotateCcw, ChevronDown } from 'lucide-react';

const PRESETS = [
  'Finance Ministry eliminates all income tax for senior citizens over 60',
  'India successfully tested a hypersonic missile last week',
  'WHO declares new global health emergency over avian flu outbreak',
  '5G towers are linked to increased cancer rates in urban areas',
];

const PIPELINE_OPTIONS = ['LangGraph', 'CrewAI', 'AutoGen'];
const MODEL_OPTIONS = ['GPT-4o', 'Claude 3.5', 'Gemini 1.5 Pro'];

const STAGE_LABELS = {
  queued:     'Queuing claim…',
  decomposing:'Decomposing into sub-claims…',
  proponent:  'Proponent agent gathering support…',
  skeptic:    'Skeptic agent gathering counter-evidence…',
  judging:    'Deterministic judge evaluating…',
  completed:  'Finalizing verdict…',
};

/**
 * ClaimInput — Large input card with:
 * - Big textarea
 * - Outlined preset chips (left of footer)
 * - Solid teal circular "go" button (right of footer)
 * - Utility bar below: pipeline + model selectors, method text
 * - Loading bar + stage label while processing
 */
export default function ClaimInput({ onVerify, loading, currentStage, elapsedTime }) {
  const [text, setText] = useState('');
  const [pipeline, setPipeline] = useState('LangGraph');
  const [model, setModel] = useState('GPT-4o');
  const textareaRef = useRef(null);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (trimmed && !loading) {
      onVerify(trimmed);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handlePreset = (preset) => {
    setText(preset);
    textareaRef.current?.focus();
  };

  const handlePipelineCycle = () => {
    const idx = PIPELINE_OPTIONS.indexOf(pipeline);
    setPipeline(PIPELINE_OPTIONS[(idx + 1) % PIPELINE_OPTIONS.length]);
  };

  const handleModelCycle = () => {
    const idx = MODEL_OPTIONS.indexOf(model);
    setModel(MODEL_OPTIONS[(idx + 1) % MODEL_OPTIONS.length]);
  };

  const stageLabel = STAGE_LABELS[currentStage] || 'Processing…';

  return (
    <section aria-label="Claim input" style={{ marginBottom: 0 }}>
      {/* Headline */}
      <h1 className="claim-headline">Audit any claim.</h1>
      <p className="claim-subline">
        Paste a headline, quote, or rumour below — our pipeline will find the truth.
      </p>

      {/* Input card */}
      <div className="claim-card" role="form" aria-label="Claim submission form">
        <textarea
          ref={textareaRef}
          id="claim-textarea"
          className="claim-textarea"
          placeholder="Paste a claim, headline, or quote…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={4}
          aria-label="Claim text input"
          aria-describedby="claim-footer-hint"
        />

        {/* Card footer */}
        <div className="claim-card-footer">
          {/* Preset chips — outlined, never filled */}
          <div className="preset-chips" id="claim-footer-hint" aria-label="Example claims">
            {PRESETS.map((p) => (
              <button
                key={p}
                className="preset-chip"
                onClick={() => handlePreset(p)}
                disabled={loading}
                title={p}
                aria-label={`Use example: ${p.slice(0, 40)}…`}
              >
                {p.slice(0, 28)}…
              </button>
            ))}
          </div>

          {/* Go button — solid teal circle */}
          <button
            id="submit-claim-btn"
            className="go-button"
            onClick={handleSubmit}
            disabled={loading || !text.trim()}
            aria-label="Submit claim for audit"
            title="Audit claim (Ctrl+Enter)"
          >
            <RotateCcw size={17} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div aria-live="polite" aria-label="Pipeline status">
          <div className="loading-bar" style={{ marginTop: 14 }}>
            <div className="loading-bar-fill" />
          </div>
          <p className="stage-label">
            {stageLabel}
            {elapsedTime > 0 && (
              <span style={{ marginLeft: 8, color: '#c4b5b0' }}>{elapsedTime}s</span>
            )}
          </p>
        </div>
      )}

      {/* Utility bar — pipeline / model / method */}
      <div className="utility-bar">
        <div className="utility-bar-left">
          <button
            className="utility-selector"
            onClick={handlePipelineCycle}
            aria-label={`Pipeline: ${pipeline}. Click to change.`}
          >
            <ChevronDown size={13} strokeWidth={1.8} />
            <span>Pipeline · {pipeline}</span>
          </button>
          <button
            className="utility-selector"
            onClick={handleModelCycle}
            aria-label={`Model: ${model}. Click to change.`}
          >
            <ChevronDown size={13} strokeWidth={1.8} />
            <span>Model · {model}</span>
          </button>
        </div>
        <span className="utility-method">
          Multi-agent debate · Cross-encoder NLI · Deterministic judge
        </span>
      </div>
    </section>
  );
}
