import React, { useState, useEffect, useRef } from 'react';
import ProvenanceGraph from './components/ProvenanceGraph';
import SidePanel from './components/SidePanel';
import ClaimInput from './components/ClaimInput';
import VerdictBanner from './components/VerdictBanner';
import FeedbackCard from './components/FeedbackCard';
import AdminFeedbackModal from './components/AdminFeedbackModal';
import { Scale, ShieldCheck, Flag, Network, Sparkles, Terminal } from 'lucide-react';

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
        evidence_count: 5,
        supporting_count: 0,
        refuting_count: 4,
        neutral_count: 1
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
  const [jobData, setJobData] = useState(INITIAL_DEMO_JOB);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState('queued');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' or 'raw_json'

  const timerRef = useRef(null);

  // Verification Pipeline Trigger & Polling
  const handleVerifyClaim = async (claimText) => {
    setLoading(true);
    setCurrentStage('queued');
    setElapsedTime(0);
    setSelectedNode(null);

    // Start timer counter
    const startTime = Date.now();
    if (timerRef.current) clearInterval(timerRef.current);
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
        throw new Error(`Failed to submit claim (HTTP ${response.status})`);
      }

      const initialData = await response.json();

      // Case A: Instant Cache Hit!
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
      alert(`Verification error: ${err.message}`);
    }
  };

  const pollJobStatus = async (jobId) => {
    const maxPollAttempts = 120; // 2 minutes max
    let attempts = 0;

    const pollInterval = setInterval(async () => {
      attempts += 1;
      try {
        const res = await fetch(`/api/verify/${jobId}`);
        if (!res.ok) {
          throw new Error(`Poll returned HTTP ${res.status}`);
        }
        const data = await res.json();

        if (data.stage) {
          setCurrentStage(data.stage);
        }

        if (data.status === 'completed') {
          clearInterval(pollInterval);
          clearInterval(timerRef.current);
          setJobData(data);
          setLoading(false);
        } else if (data.status === 'failed') {
          clearInterval(pollInterval);
          clearInterval(timerRef.current);
          setLoading(false);
          alert(`Pipeline failed: ${data.error || 'Unknown error'}`);
        } else if (attempts >= maxPollAttempts) {
          clearInterval(pollInterval);
          clearInterval(timerRef.current);
          setLoading(false);
          alert('Verification timed out after 120 seconds.');
        }
      } catch (pollErr) {
        console.error('Polling error:', pollErr);
      }
    }, 1000);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e17', color: '#f8fafc', paddingBottom: '60px' }}>
      {/* Top Navigation Header */}
      <header
        style={{
          borderBottom: '1px solid #1e293b',
          background: 'rgba(11, 15, 25, 0.85)',
          backdropFilter: 'blur(12px)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          padding: '14px 28px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0284c7, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.4)',
            }}
          >
            <Scale size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', color: '#ffffff' }}>
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
            <span>{activeTab === 'graph' ? 'View API JSON' : 'View Graph'}</span>
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

      {/* Main Container */}
      <main style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Verification Input & Demo Presets */}
        <ClaimInput
          onVerify={handleVerifyClaim}
          loading={loading}
          currentStage={currentStage}
          elapsedTime={elapsedTime}
        />

        {/* Aggregated Verdict Banner */}
        <VerdictBanner jobData={jobData} />

        {/* Content Area: Provenance Graph + Inspector SidePanel */}
        {activeTab === 'graph' ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.8fr) minmax(360px, 1fr)',
              gap: '20px',
              height: '580px',
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
          <div className="glass-panel" style={{ padding: '20px', maxHeight: '560px', overflowY: 'auto' }}>
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

        {/* Feedback Card (Thumbs up/down loop for the current verdict) */}
        <FeedbackCard
          jobId={jobData?.job_id}
          verdict={jobData?.result?.verdict}
          onFeedbackSubmitted={(fb) => {
            console.log('Feedback submitted:', fb);
          }}
        />
      </main>

      {/* Admin Flags Review Modal */}
      <AdminFeedbackModal isOpen={adminModalOpen} onClose={() => setAdminModalOpen(false)} />
    </div>
  );
}
