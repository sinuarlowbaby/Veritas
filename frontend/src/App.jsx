import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Layout components
import IconRail from './components/IconRail';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';

// View components
import ClaimInput from './components/ClaimInput';
import VerdictHeader from './components/VerdictHeader';
import FeedbackRow from './components/FeedbackRow';
import EvidenceView from './components/EvidenceView';
import ProvenanceGraph from './components/ProvenanceGraph';
import HistoryView from './components/HistoryView';

const STORAGE_KEY = 'veritas_latest_verification_job';
const HISTORY_KEY = 'veritas_history';

const INITIAL_DEMO_JOB = {
  job_id: 'job_01df49be2a65',
  status: 'completed',
  stage: 'completed',
  cached: false,
  latency_ms: 20499,
  token_count: 1055,
  result: {
    claim: 'Finance Ministry eliminates all income tax for senior citizens over 60 starting April 1',
    verdict: 'FALSE',
    confidence: 0.998,
    score: -0.998,
    is_abstained: false,
    explanation:
      'Official Ministry of Finance and Income Tax Department notifications confirm that income tax slabs for senior citizens continue under both tax regimes. Viral claims asserting complete tax elimination are unfounded rumors without any legislative or gazette backing.',
    key_citations: [
      'https://incometax.gov.in/rules',
      'https://pib.gov.in/factcheck/senior-tax',
    ],
    sub_claims: [
      {
        id: 'subclaim_1',
        text: 'Finance Ministry announced elimination of income tax for citizens over 60',
        verdict: 'FALSE',
        confidence: 0.998,
        score: -0.998,
        evidence_count: 3,
        supporting_count: 0,
        refuting_count: 3,
        neutral_count: 0,
      },
      {
        id: 'subclaim_2',
        text: 'Exemption from income tax takes effect starting April 1',
        verdict: 'FALSE',
        confidence: 0.95,
        score: -0.95,
        evidence_count: 2,
        supporting_count: 0,
        refuting_count: 2,
        neutral_count: 0,
      },
    ],
    evidence: [
      {
        evidence_id: 'ev_001',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote:
          'The Finance Ministry has clarified that no such proposal to eliminate income tax for senior citizens over 60 exists; standard slab rates continue to apply.',
        source_url: 'https://pib.gov.in/factcheck/senior-tax',
        domain: 'pib.gov.in',
        domain_tier: 1,
        nli_label: 'REFUTES',
        nli_confidence: 0.999,
        retrieved_by: 'skeptic',
      },
      {
        evidence_id: 'ev_002',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote:
          'Income tax slabs and rebate limits under section 87A remain as codified in the Finance Act, with senior citizens retaining standard deductions.',
        source_url: 'https://incometax.gov.in/rules',
        domain: 'incometax.gov.in',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.994,
        retrieved_by: 'skeptic',
      },
      {
        evidence_id: 'ev_003',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote:
          'Posts on social media claiming senior citizens are exempt from paying income tax from April 1 are misleading and fake, PIB Fact Check confirmed.',
        source_url: 'https://thehindu.com/news/national/fact-check-tax-rumor',
        domain: 'thehindu.com',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.985,
        retrieved_by: 'proponent',
      },
      {
        evidence_id: 'ev_004',
        sub_claim_id: 'subclaim_2',
        sub_claim: 'Exemption from income tax takes effect starting April 1',
        quote:
          'The assessment year starting April 1 maintains existing tax rates for individual assesses aged 60 and above without exemption blanket.',
        source_url: 'https://economictimes.indiatimes.com/wealth/tax/slabs',
        domain: 'economictimes.indiatimes.com',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.991,
        retrieved_by: 'skeptic',
      },
      {
        evidence_id: 'ev_005',
        sub_claim_id: 'subclaim_2',
        sub_claim: 'Exemption from income tax takes effect starting April 1',
        quote:
          'Viral message claims zero tax liability for elders from next fiscal year; revenue department issues categorical denial.',
        source_url: 'https://boomlive.in/fact-check/senior-citizen-tax-fake',
        domain: 'boomlive.in',
        domain_tier: 1,
        nli_label: 'REFUTES',
        nli_confidence: 0.997,
        retrieved_by: 'skeptic',
      },
    ],
  },
};

export default function App() {
  // Persistent job state
  const [jobData, setJobData] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.result) return parsed;
      }
    } catch { /* ignore */ }
    return INITIAL_DEMO_JOB;
  });

  // History (persisted)
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(HISTORY_KEY);
      if (saved) return JSON.parse(saved);
    } catch { /* ignore */ }
    return [INITIAL_DEMO_JOB];
  });

  // UI state
  const [activeView, setActiveView] = useState('audit');
  const [loading, setLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState('queued');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [error, setError] = useState(null);
  const [lastClaim, setLastClaim] = useState('');

  const timerRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Sync job to localStorage
  useEffect(() => {
    if (jobData?.status === 'completed' && jobData.result) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(jobData));
      } catch { /* ignore */ }
    }
  }, [jobData]);

  // Sync history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 20)));
    } catch { /* ignore */ }
  }, [history]);

  // Cleanup timers
  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
  }, []);

  // ─── Verification pipeline ───────────────────────────────────────────────

  const handleVerifyClaim = async (claimText) => {
    setError(null);
    setLastClaim(claimText);
    setLoading(true);
    setCurrentStage('queued');
    setElapsedTime(0);
    setActiveView('audit');

    if (timerRef.current) clearInterval(timerRef.current);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

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

      if (initialData.status === 'completed' && initialData.result) {
        clearInterval(timerRef.current);
        setJobData(initialData);
        setLoading(false);
        addToHistory(initialData);
        return;
      }

      pollJobStatus(initialData.job_id);
    } catch (err) {
      clearInterval(timerRef.current);
      setLoading(false);
      setError(err.message || 'Failed to submit verification job.');
    }
  };

  const pollJobStatus = (jobId) => {
    const maxAttempts = 120;
    let attempts = 0;

    pollIntervalRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const res = await fetch(`/api/verify/${jobId}`);
        if (!res.ok) throw new Error(`Poll HTTP ${res.status}`);
        const data = await res.json();

        if (data.stage) setCurrentStage(data.stage);

        if (data.status === 'completed' && data.result) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setJobData(data);
          setLoading(false);
          addToHistory(data);
        } else if (data.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(data.error || 'The verification pipeline encountered a failure.');
        } else if (attempts >= maxAttempts) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError('Verification timed out after 120 seconds.');
        }
      } catch (pollErr) {
        if (attempts >= maxAttempts) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(`Network error while polling: ${pollErr.message}`);
        }
      }
    }, 1000);
  };

  const addToHistory = (data) => {
    setHistory((prev) => {
      const filtered = prev.filter((h) => h.job_id !== data.job_id);
      return [data, ...filtered].slice(0, 20);
    });
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
              onSelect={(item) => {
                setJobData(item);
                setActiveView('audit');
              }}
            />
          </div>
        );

      case 'settings':
        return (
          <div key="settings" className="view-container centered-col">
            <h2 className="view-title">Settings</h2>
            <p className="view-subtitle" style={{ marginBottom: 0 }}>
              Configuration options will appear here in a future release.
            </p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      {/* 58px fixed icon rail */}
      <IconRail activeView={activeView} onNavigate={setActiveView} />

      {/* 52px fixed top bar */}
      <TopBar jobId={jobData?.job_id} pipelineStatus="healthy" />

      {/* Main scrollable area */}
      <main className="main-content" id="main-content">
        {renderView()}
      </main>

      {/* Mobile bottom nav */}
      <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
        {[
          { id: 'audit', label: 'Audit' },
          { id: 'evidence', label: 'Evidence' },
          { id: 'provenance', label: 'Graph' },
          { id: 'history', label: 'History' },
        ].map(({ id, label }) => (
          <button
            key={id}
            className={`mobile-nav-btn ${activeView === id ? 'active' : ''}`}
            onClick={() => setActiveView(id)}
            aria-label={label}
          >
            <span style={{ fontSize: 18 }}>
              {id === 'audit' ? '🛡' : id === 'evidence' ? '📄' : id === 'provenance' ? '🕸' : '🕐'}
            </span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
