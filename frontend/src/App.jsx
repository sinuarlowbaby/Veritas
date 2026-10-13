import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Layout
import HistorySidebar from './components/HistorySidebar';
import TopBar from './components/TopBar';
import ErrorBanner from './components/ErrorBanner';
import AuthModal from './components/AuthModal';

// View components
import ClaimInput from './components/ClaimInput';
import VerdictHeader from './components/VerdictHeader';
import FeedbackRow from './components/FeedbackRow';
import EvidenceView from './components/EvidenceView';
import ProvenanceGraph from './components/ProvenanceGraph';
import HistoryView from './components/HistoryView';

// Utilities
import { classifyError } from './utils/classifyError';

import { Shield } from 'lucide-react';

const HISTORY_KEY = 'veritas_history';
const GUEST_HISTORY_KEY = 'veritas_guest_history';
const TOKEN_KEY = 'veritas_token';
const USER_KEY = 'veritas_user';

export default function App() {
  // ─── Authentication state (Multi-device persistence) ─────────────────────
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem(TOKEN_KEY) || null;
    } catch {
      return null;
    }
  });

  const [user, setUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem(USER_KEY);
      return savedUser ? JSON.parse(savedUser) : null;
    } catch {
      return null;
    }
  });

  const [authModalOpen, setAuthModalOpen] = useState(false);

  // ─── Audit History (Synced with Database for authenticated users) ─────────
  const [history, setHistory] = useState(() => {
    try {
      const activeKey = localStorage.getItem(TOKEN_KEY) ? HISTORY_KEY : GUEST_HISTORY_KEY;
      const saved = localStorage.getItem(activeKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch { /* ignore */ }
    return [];
  });

  // Currently selected / displayed job
  const [jobData, setJobData] = useState(null);

  // True when the displayed job was loaded from history (not a fresh pipeline run).
  const [isHistoricalJob, setIsHistoricalJob] = useState(false);

  // UI state
  const [activeView, setActiveView] = useState('audit');
  const [loading, setLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState('queued');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [error, setError] = useState(null);
  const [lastClaim, setLastClaim] = useState('');

  const timerRef = useRef(null);
  const pollRef = useRef(null);

  // Persist history locally based on authentication state
  useEffect(() => {
    try {
      const activeKey = token ? HISTORY_KEY : GUEST_HISTORY_KEY;
      localStorage.setItem(activeKey, JSON.stringify(history.slice(0, 50)));
    } catch { /* ignore */ }
  }, [history, token]);

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setJobData(null);
    setIsHistoricalJob(false);
    setActiveView('audit');
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(HISTORY_KEY);
      // Load clean guest history (or empty if none)
      const guestSaved = localStorage.getItem(GUEST_HISTORY_KEY);
      if (guestSaved) {
        const parsed = JSON.parse(guestSaved);
        setHistory(Array.isArray(parsed) ? parsed : []);
      } else {
        setHistory([]);
      }
    } catch {
      setHistory([]);
    }
  };

  // Sync guest tasks performed without login to the user's database account
  const syncGuestTasksToDb = async (authToken) => {
    try {
      const guestSaved = localStorage.getItem(GUEST_HISTORY_KEY);
      const guestList = guestSaved ? JSON.parse(guestSaved) : [];
      const guestJobIds = Array.isArray(guestList)
        ? guestList.map((g) => g.job_id).filter(Boolean)
        : [];

      if (guestJobIds.length > 0) {
        // Send guest job_ids to /api/history/sync to link them to the logged-in user in DB
        const syncRes = await fetch('/api/history/sync', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({ job_ids: guestJobIds }),
        });

        // Clear guest history now that tasks are merged into database account
        localStorage.removeItem(GUEST_HISTORY_KEY);

        if (syncRes.ok) {
          const mergedDbJobs = await syncRes.json();
          if (Array.isArray(mergedDbJobs)) {
            const formatted = mergedDbJobs.map((h) => ({
              ...h,
              _timestamp: h.created_at ? new Date(h.created_at).getTime() : Date.now(),
            }));
            setHistory(formatted);
            return;
          }
        }
      }

      // If no guest tasks or sync failed, fetch regular user history from DB
      const histRes = await fetch('/api/history', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (histRes.ok) {
        const dbItems = await histRes.json();
        if (Array.isArray(dbItems)) {
          const formatted = dbItems.map((h) => ({
            ...h,
            _timestamp: h.created_at ? new Date(h.created_at).getTime() : Date.now(),
          }));
          setHistory(formatted);
        }
      }
    } catch (err) {
      console.warn('Could not sync guest tasks or history:', err);
    }
  };

  // Sync / Verify Authentication & Fetch Persistent Database History on mount
  useEffect(() => {
    const syncAuthAndHistory = async () => {
      if (!token) return;
      try {
        const meRes = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!meRes.ok) {
          // Token expired or invalid
          handleLogout();
          return;
        }

        const userData = await meRes.json();
        setUser(userData);
        localStorage.setItem(USER_KEY, JSON.stringify(userData));

        // Sync any guest tasks performed prior to login and pull DB history
        await syncGuestTasksToDb(token);
      } catch (err) {
        console.warn('Could not sync user profile:', err);
      }
    };

    syncAuthAndHistory();
  }, [token]);

  // Cleanup timers on unmount
  useEffect(() => () => {
    clearInterval(timerRef.current);
    clearInterval(pollRef.current);
  }, []);

  // ─── Helpers ─────────────────────────────────────────────────────────────

  const handleAuthSuccess = async (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    try {
      localStorage.setItem(TOKEN_KEY, newToken);
      localStorage.setItem(USER_KEY, JSON.stringify(newUser));
      // Migrate guest audits to DB account & load fresh user history
      await syncGuestTasksToDb(newToken);
    } catch { /* ignore */ }
  };

  const addToHistory = (data) => {
    const entry = { ...data, _timestamp: Date.now() };
    setHistory((prev) => {
      const deduped = prev.filter((h) => h.job_id !== data.job_id);
      return [entry, ...deduped].slice(0, 50);
    });

    // If user is guest (unauthenticated), persist immediately to GUEST_HISTORY_KEY
    if (!token) {
      try {
        const guestSaved = localStorage.getItem(GUEST_HISTORY_KEY);
        const prevGuest = guestSaved ? JSON.parse(guestSaved) : [];
        const dedupedGuest = [entry, ...prevGuest.filter((h) => h.job_id !== data.job_id)].slice(0, 50);
        localStorage.setItem(GUEST_HISTORY_KEY, JSON.stringify(dedupedGuest));
      } catch { /* ignore */ }
    }

    return entry;
  };

  const handleNewAudit = () => {
    setJobData(null);
    setIsHistoricalJob(false);
    setError(null);
    setActiveView('audit');
  };

  // ─── Select a history item → load it and jump to audit view ──────────────
  const handleSelectHistory = async (item) => {
    if (!item) return;
    setIsHistoricalJob(true);
    setError(null);
    setActiveView('audit');

    // If full result object with verdict is already present, display immediately
    if (item.result && item.result.verdict) {
      setJobData(item);
      return;
    }

    // If result details are missing (e.g. shallow DB history row), fetch full details
    if (item.job_id) {
      setLoading(true);
      try {
        const res = await fetch(`/api/history/${item.job_id}`);
        if (res.ok) {
          const fullData = await res.json();
          setJobData({
            ...fullData,
            cached: item.cached ?? fullData.cached,
            cache_type: item.cache_type ?? fullData.cache_type,
            similarity: item.similarity ?? fullData.similarity,
          });
        } else {
          const vRes = await fetch(`/api/verify/${item.job_id}`);
          if (vRes.ok) {
            const fullData = await vRes.json();
            setJobData(fullData);
          } else {
            setJobData(item);
          }
        }
      } catch {
        setJobData(item);
      } finally {
        setLoading(false);
      }
    } else {
      setJobData(item);
    }
  };

  // ─── Re-audit a historical claim ─────────────────────────────────────────
  const handleReaudit = (claimText) => {
    handleVerifyClaim(claimText);
  };

  // ─── Submit new claim ─────────────────────────────────────────────────────
  const handleVerifyClaim = async (claimText) => {
    setError(null);
    setLastClaim(claimText);
    setLoading(true);
    setJobData(null);
    setIsHistoricalJob(false);
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
      // Include Bearer token if user is signed in to link audit to their database account
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch('/api/verify', {
        method: 'POST',
        headers,
        body: JSON.stringify({ claim: claimText }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        const rawMsg = errJson.detail || `Server returned HTTP ${response.status}`;
        throw Object.assign(new Error(rawMsg), { httpStatus: response.status });
      }

      const initialData = await response.json();

      // Case A: Instant cache hit (Exact or Semantic Caching)
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
      setError(classifyError(err.message, err.httpStatus ?? null));
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
          setError(classifyError(data.error || 'The verification pipeline encountered a failure.'));
        } else if (attempts >= maxAttempts) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(classifyError('Verification timed out after 120 seconds.'));
        }
      } catch (pollErr) {
        if (attempts >= maxAttempts) {
          clearInterval(pollRef.current);
          clearInterval(timerRef.current);
          setLoading(false);
          setError(classifyError(pollErr.message));
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
                <VerdictHeader
                  jobData={jobData}
                  onReaudit={isHistoricalJob ? handleReaudit : undefined}
                />
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
                  retrieves curated RAG facts and live web evidence to render a verified verdict.
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
            <p className="view-subtitle" style={{ marginBottom: 16 }}>
              Database & Pipeline Configuration
            </p>
            <div style={{ background: 'var(--bg-off)', border: '1px solid var(--border)', borderRadius: 8, padding: 18, fontSize: 13, lineHeight: 1.6 }}>
              <p><strong>Database:</strong> PostgreSQL (pgvector active) / SQLite persistent fallback</p>
              <p><strong>Semantic Caching:</strong> Enabled (Cosine similarity threshold: 0.88)</p>
              <p><strong>Account:</strong> {user ? `Signed in as ${user.username} (${user.email})` : 'Anonymous session (audits stored locally)'}</p>
            </div>
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

      {/* Thin top bar with User Account Login / Sign Out */}
      <TopBar
        jobId={jobData?.job_id}
        pipelineStatus="healthy"
        user={user}
        onOpenAuth={() => setAuthModalOpen(true)}
        onLogout={handleLogout}
      />

      {/* Main scrollable column */}
      <main className="main-content" id="main-content">
        {renderView()}
      </main>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />

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
