import React, { useState, useEffect, useRef } from 'react';
import ProvenanceGraph from './components/ProvenanceGraph';
import SidePanel from './components/SidePanel';
import ClaimInput from './components/ClaimInput';
import VerdictBanner from './components/VerdictBanner';
import EvidenceAuditList from './components/EvidenceAuditList';
import FeedbackCard from './components/FeedbackCard';
import AdminFeedbackModal from './components/AdminFeedbackModal';
import ErrorBanner from './components/ErrorBanner';
import { Scale, ShieldCheck, Flag, Network, Sparkles, Terminal, BookOpen, Layers } from 'lucide-react';

const STORAGE_KEY = 'veritas_latest_verification_job';

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
    explanation: 'Official Ministry of Finance and Income Tax Department notifications confirm that income tax slabs for senior citizens continue under both tax regimes. Viral claims asserting complete tax elimination are unfounded rumors without legislative backing.',
    key_citations: [
      'https://incometax.gov.in/rules',
      'https://pib.gov.in/factcheck/senior-tax'
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
        neutral_count: 0
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
        neutral_count: 0
      }
    ],
    evidence: [
      {
        evidence_id: 'ev_001',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote: 'The Finance Ministry has clarified that no such proposal to eliminate income tax for senior citizens over 60 exists; standard slab rates continue to apply.',
        source_url: 'https://pib.gov.in/factcheck/senior-tax',
        domain: 'pib.gov.in',
        domain_tier: 1,
        nli_label: 'REFUTES',
        nli_confidence: 0.999,
        retrieved_by: 'skeptic'
      },
      {
        evidence_id: 'ev_002',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote: 'Income tax slabs and rebate limits under section 87A remain as codified in the Finance Act, with senior citizens retaining standard deductions.',
        source_url: 'https://incometax.gov.in/rules',
        domain: 'incometax.gov.in',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.994,
        retrieved_by: 'skeptic'
      },
      {
        evidence_id: 'ev_003',
        sub_claim_id: 'subclaim_1',
        sub_claim: 'Finance Ministry announced elimination of income tax for citizens over 60',
        quote: 'Posts on social media claiming senior citizens are exempt from paying income tax from April 1 are misleading and fake, PIB Fact Check confirmed.',
        source_url: 'https://thehindu.com/news/national/fact-check-tax-rumor',
        domain: 'thehindu.com',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.985,
        retrieved_by: 'proponent'
      },
      {
        evidence_id: 'ev_004',
        sub_claim_id: 'subclaim_2',
        sub_claim: 'Exemption from income tax takes effect starting April 1',
        quote: 'The assessment year starting April 1 maintains existing tax rates for individual assesses aged 60 and above without exemption blanket.',
        source_url: 'https://economictimes.indiatimes.com/wealth/tax/slabs',
        domain: 'economictimes.indiatimes.com',
        domain_tier: 2,
        nli_label: 'REFUTES',
        nli_confidence: 0.991,
        retrieved_by: 'skeptic'
      },
      {
        evidence_id: 'ev_005',
        sub_claim_id: 'subclaim_2',
        sub_claim: 'Exemption from income tax takes effect starting April 1',
        quote: 'Viral message claims zero tax liability for elders from next fiscal year; revenue department issues categorical denial.',
        source_url: 'https://boomlive.in/fact-check/senior-citizen-tax-fake',
        domain: 'boomlive.in',
        domain_tier: 1,
        nli_label: 'REFUTES',
        nli_confidence: 0.997,
        retrieved_by: 'skeptic'
      }
    ]
  }
};

export default function App() {
  // Load persistent state from localStorage on refresh, or fallback to demo
  const [jobData, setJobData] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.result) return parsed;
      }
    } catch (e) {
      console.warn('Could not read saved job from localStorage:', e);
    }
    return INITIAL_DEMO_JOB;
  });

  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState('queued');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [error, setError] = useState(null);
  const [lastClaim, setLastClaim] = useState('');
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' or 'raw_json'

  const timerRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Sync to localStorage on completed state updates
  useEffect(() => {
    if (jobData && jobData.status === 'completed' && jobData.result) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(jobData));
      } catch (e) {
        console.warn('Failed to save job to localStorage:', e);
      }
    }
  }, [jobData]);

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  // Verification Pipeline Trigger & Polling
  const handleVerifyClaim = async (claimText) => {
    // Reset state for new or repeated submission
    setError(null);
    setSelectedNode(null);
    setLastClaim(claimText);
    setLoading(true);
    setCurrentStage('queued');
    setElapsedTime(0);

    // Stop any existing intervals
    if (timerRef.current) clearInterval(timerRef.current);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    // Start timer counter
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 500);

    try {
      // Step 1: Submit to POST /api/verify
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

      // Case A: Instant Cache Hit! (Second submission or already evaluated)
      if (initialData.status === 'completed' && initialData.result) {
        clearInterval(timerRef.current);
        setJobData(initialData);
        setLoading(false);
        return;
      }

      // Case B: Background Task Enqueued -> Poll GET /api/verify/{job_id}
      const jobId = initialData.job_id;
      pollJobStatus(jobId);
    } catch (err) {
      clearInterval(timerRef.current);
      setLoading(false);
      setError(err.message || 'Failed to submit verification job.');
    }
  };

  const pollJobStatus = (jobId) => {
    const maxPollAttempts = 120; // 2 minutes max before timeout
    let attempts = 0;

    pollIntervalRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const res = await fetch(`/api/verify/${jobId}`);
        if (!res.ok) {
          throw new Error(`Poll request returned HTTP ${res.status}`);
        }
        const data = await res.json();

        if (data.stage) {
          setCurrentStage(data.stage);
        }

        if (data.status === 'completed' && data.result) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setJobData(data);
          setLoading(false);
        } else if (data.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(data.error || 'The verification pipeline encountered an internal evaluation failure.');
        } else if (attempts >= maxPollAttempts) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError('Verification timed out after 120 seconds. The agents may have exceeded web retrieval quota or network limits.');
        }
      } catch (pollErr) {
        console.error('Polling error:', pollErr);
        // Continue retrying up to max attempts in case of intermittent network glitch
        if (attempts >= maxPollAttempts) {
          clearInterval(pollIntervalRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(`Network connection lost while polling job ${jobId}: ${pollErr.message}`);
        }
      }
    }, 1000);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e17', color: '#f8fafc', paddingBottom: '60px', overflowX: 'hidden' }}>
      {/* Top Navigation Header */}
      <header
        style={{
          borderBottom: '1px solid #1e293b',
          background: 'rgba(11, 15, 25, 0.9)',
          backdropFilter: 'blur(12px)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '9px',
              background: 'linear-gradient(135deg, #0284c7, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.4)',
            }}
          >
            <Scale size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '17px', fontWeight: '800', letterSpacing: '-0.02em', color: '#ffffff' }}>
                VERITAS
              </h1>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                PROVENANCE AUDIT
              </span>
            </div>
            <p style={{ fontSize: '11px', color: '#94a3b8' }}>
              Multi-Agent Debate • Cross-Encoder NLI • Deterministic Judge
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => setActiveTab(activeTab === 'graph' ? 'raw_json' : 'graph')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: '#1e293b',
              color: '#cbd5e1',
              borderRadius: '8px',
              border: '1px solid #334155',
              fontSize: '12px',
              fontWeight: '500',
            }}
          >
            <Terminal size={14} />
            <span>{activeTab === 'graph' ? 'Inspect API JSON' : 'Back to Graph'}</span>
          </button>

          <button
            onClick={() => setAdminModalOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'rgba(239, 68, 68, 0.12)',
              color: '#f87171',
              borderRadius: '8px',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              fontSize: '12px',
              fontWeight: '600',
            }}
          >
            <Flag size={14} />
            <span>Review Flags & Feedback</span>
          </button>
        </div>
      </header>

      {/* Main Container (Balanced for 13-16 inch laptop screens) */}
      <main style={{ maxWidth: '1360px', margin: '0 auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Verification Input & Demo Presets */}
        <ClaimInput
          onVerify={handleVerifyClaim}
          loading={loading}
          currentStage={currentStage}
          elapsedTime={elapsedTime}
        />

        {/* Error Notice (if timeout or failure) */}
        {error && (
          <ErrorBanner
            error={error}
            onRetry={() => lastClaim && handleVerifyClaim(lastClaim)}
            onDismiss={() => setError(null)}
          />
        )}

        {/* Aggregated Verdict Banner */}
        <VerdictBanner jobData={jobData} />

        {/* Primary View: Cytoscape Provenance Graph + Node Audit Inspector */}
        {activeTab === 'graph' ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.8fr) minmax(340px, 1fr)',
              gap: '18px',
              height: 'clamp(460px, 52vh, 560px)',
            }}
          >
            {/* Cytoscape 3-Layer Graph */}
            <div style={{ height: '100%' }}>
              <ProvenanceGraph
                result={jobData?.result}
                onSelectNode={(node) => setSelectedNode(node)}
                selectedNodeId={selectedNode?.id}
              />
            </div>

            {/* Click-and-Audit Side Panel */}
            <div style={{ height: '100%' }}>
              <SidePanel selectedNode={selectedNode} overallResult={jobData?.result} />
            </div>
          </div>
        ) : (
          /* Raw API Response View to verify Frontend is a pure Dumb Renderer */
          <div className="glass-panel" style={{ padding: '20px', maxHeight: '520px', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h4 style={{ fontSize: '13px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: '700' }}>
                Full Verification Job Response JSON (Dumb Renderer Output)
              </h4>
              <span style={{ fontSize: '11px', color: '#38bdf8' }}>
                GET /api/verify/{jobData?.job_id}
              </span>
            </div>
            <pre
              style={{
                background: '#090d16',
                padding: '16px',
                borderRadius: '8px',
                fontSize: '12px',
                color: '#38bdf8',
                lineHeight: '1.4',
                overflowX: 'auto',
              }}
            >
              {JSON.stringify(jobData, null, 2)}
            </pre>
          </div>
        )}

        {/* Verbatim Evidence & Sub-claims Audit Trail (Directly Visible, Never Hidden) */}
        <EvidenceAuditList
          result={jobData?.result}
          onSelectNode={(node) => setSelectedNode(node)}
          selectedNodeId={selectedNode?.id}
        />

        {/* Feedback Card (Thumbs up/down loop for the current verdict) */}
        <FeedbackCard
          jobId={jobData?.job_id}
          verdict={jobData?.result?.verdict}
          onFeedbackSubmitted={(fb) => {
            console.log('Feedback recorded for job:', fb);
          }}
        />
      </main>

      {/* Admin Flags Review Modal */}
      <AdminFeedbackModal isOpen={adminModalOpen} onClose={() => setAdminModalOpen(false)} />
    </div>
  );
}
