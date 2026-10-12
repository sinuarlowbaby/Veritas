import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Layout
import HistorySidebar from './components/HistorySidebar';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';

// View components
import ClaimInput from './components/ClaimInput';
import VerdictHeader from './components/VerdictHeader';
import FeedbackRow from './components/FeedbackRow';
import EvidenceView from './components/EvidenceView';
import ProvenanceGraph from './components/ProvenanceGraph';
import HistoryView from './components/HistoryView';

import { Shield } from 'lucide-react';

const HISTORY_KEY = 'veritas_history';

export default function App() {
  // ─── Real history only — no dummy data ───────────────────────────────────
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(HISTORY_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch { /* ignore */ }
    return [];
  });

  // Currently selected / displayed job
  const [jobData, setJobData] = useState(null);

  // UI state
  const [activeView, setActiveView] = useState('audit');
  const [loading, setLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState('queued');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [error, setError] = useState(null);
  const [lastClaim, setLastClaim] = useState('');

  const timerRef = useRef(null);
  const pollRef = useRef(null);

  // Persist history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 30)));
    } catch { /* ignore */ }
  }, [history]);

  // Cleanup timers on unmount
  useEffect(() => () => {
    clearInterval(timerRef.current);
    clearInterval(pollRef.current);
  }, []);

  // ─── Helpers ─────────────────────────────────────────────────────────────

  const addToHistory = (data) => {
    const entry = { ...data, _timestamp: Date.now() };
    setHistory((prev) => {
      const deduped = prev.filter((h) => h.job_id !== data.job_id);
      return [entry, ...deduped].slice(0, 30);
    });
    return entry;
  };

  const handleNewAudit = () => {
    setJobData(null);
    setError(null);
    setActiveView('audit');
  };

  // ─── Select a history item → load it and jump to audit view ──────────────
  const handleSelectHistory = (item) => {
    setJobData(item);
    setError(null);
    setActiveView('audit');
  };

  // ─── Submit new claim ─────────────────────────────────────────────────────
  const handleVerifyClaim = async (claimText) => {
    setError(null);
    setLastClaim(claimText);
    setLoading(true);
    setJobData(null);
    setCurrentStage('queued');
    setElapsedTime(0);
    setActiveView('audit');

    clearInterval(timerRef.current);
    clearInterval(pollRef.current);

    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 500);

    try {
      const response = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: claimText }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned HTTP ${response.status}`);
      }

      const initialData = await response.json();

      // Case A: Instant cache hit
      if (initialData.status === 'completed' && initialData.result) {
        clearInterval(timerRef.current);
        const entry = addToHistory(initialData);
        setJobData(entry);
        setLoading(false);
        return;
      }

      // Case B: Background job → poll
      pollJobStatus(initialData.job_id);
    } catch (err) {
      clearInterval(timerRef.current);
      setLoading(false);
      setError(err.message || 'Failed to submit the verification job.');
    }
  };

  const pollJobStatus = (jobId) => {
    const maxAttempts = 120;
    let attempts = 0;

    pollRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const res = await fetch(`/api/verify/${jobId}`);
        if (!res.ok) throw new Error(`Poll HTTP ${res.status}`);
        const data = await res.json();

        if (data.stage) setCurrentStage(data.stage);

        if (data.status === 'completed' && data.result) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          const entry = addToHistory(data);
          setJobData(entry);
          setLoading(false);
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(data.error || 'The verification pipeline encountered a failure.');
        } else if (attempts >= maxAttempts) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError('Verification timed out after 120 seconds.');
        }
      } catch (pollErr) {
        if (attempts >= maxAttempts) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(`Network error: ${pollErr.message}`);
        }
      }
    }, 1000);
  };

  // ─── View rendering ───────────────────────────────────────────────────────
  const renderView = () => {
    switch (activeView) {
      case 'audit':
        return (
          <div key="audit" className="view-container centered-col">
            <ClaimInput
              onVerify={handleVerifyClaim}
              loading={loading}
              currentStage={currentStage}
              elapsedTime={elapsedTime}
            />

            {error && (
              <ErrorBanner
                error={error}
                onRetry={() => lastClaim && handleVerifyClaim(lastClaim)}
                onDismiss={() => setError(null)}
              />
            )}

            {/* Results — only show real data */}
            {jobData?.result && !loading && (
              <>
                <VerdictHeader jobData={jobData} />
                <FeedbackRow
                  jobId={jobData.job_id}
                  verdict={jobData.result.verdict}
                  onFeedbackSubmitted={(fb) => console.log('Feedback:', fb)}
                />
              </>
            )}

            {/* Empty state — no result yet, not loading */}
            {!jobData && !loading && !error && (
              <div className="audit-empty-state">
                <div className="audit-empty-icon">
                  <Shield size={20} color="var(--text-muted)" strokeWidth={1.5} />
                </div>
                <p className="audit-empty-title">Ready to audit</p>
                <p className="audit-empty-sub">
                  Enter a headline, quote, or claim above. Our multi-agent pipeline
                  will find supporting and refuting evidence, then render a verdict.
                </p>
              </div>
            )}
          </div>
        );

      case 'evidence':
        return (
          <div key="evidence" className="view-container centered-col">
            <EvidenceView result={jobData?.result} />
          </div>
        );

      case 'provenance':
        return (
          <div key="provenance" className="view-container centered-col">
            <ProvenanceGraph result={jobData?.result} />
          </div>
        );

      case 'history':
        return (
          <div key="history" className="view-container centered-col">
            <HistoryView
              history={history}
              onSelect={handleSelectHistory}
            />
          </div>
        );

      case 'settings':
        return (
          <div key="settings" className="view-container centered-col">
            <h2 className="view-title">Settings</h2>
            <p className="view-subtitle" style={{ marginBottom: 0 }}>
              Pipeline configuration will appear here in a future release.
            </p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      {/* Two-panel sidebar: icon strip (50px) + history panel (220px) */}
      <HistorySidebar
        history={history}
        activeJobId={jobData?.job_id}
        activeView={activeView}
        onNavigate={setActiveView}
        onSelectHistory={handleSelectHistory}
        onNewAudit={handleNewAudit}
      />

      {/* Thin top bar */}
      <TopBar
        jobId={jobData?.job_id}
        pipelineStatus="healthy"
      />

      {/* Main scrollable column */}
      <main className="main-content" id="main-content">
        {renderView()}
      </main>

      {/* Mobile bottom nav */}
      <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
        {[
          { id: 'audit',      emoji: '🛡', label: 'Audit' },
          { id: 'evidence',   emoji: '📄', label: 'Evidence' },
          { id: 'provenance', emoji: '🕸', label: 'Graph' },
          { id: 'history',    emoji: '🕐', label: 'History' },
        ].map(({ id, emoji, label }) => (
          <button
            key={id}
            className={`mobile-nav-btn ${activeView === id ? 'active' : ''}`}
            onClick={() => setActiveView(id)}
            aria-label={label}
          >
            <span style={{ fontSize: 18 }}>{emoji}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
