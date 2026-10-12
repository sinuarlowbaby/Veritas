import React, { useState } from 'react';
import { Search, Plus, Shield, FileText, GitFork, Clock, Settings, ChevronDown } from 'lucide-react';
import { VerdictDot, verdictClass, verdictLabel } from './VerdictDot';

/**
 * HistorySidebar — 220px panel showing real audit history.
 * Matches reference: title + search + "New Audit" CTA + grouped recents list.
 * No dummy data — shows empty state when history is empty.
 */
export default function HistorySidebar({
  history,
  activeJobId,
  activeView,
  onNavigate,
  onSelectHistory,
  onNewAudit,
}) {
  const [search, setSearch] = useState('');

  const filtered = history.filter((item) => {
    if (!search.trim()) return true;
    const claim = (item.result?.claim || '').toLowerCase();
    const verdict = (item.result?.verdict || '').toLowerCase();
    return claim.includes(search.toLowerCase()) || verdict.includes(search.toLowerCase());
  });

  // Group by: today / this week / older
  const now = Date.now();
  const DAY = 86400000;
  const WEEK = 7 * DAY;

  const grouped = {
    today: [],
    week: [],
    older: [],
  };

  filtered.forEach((item) => {
    const ts = item._timestamp || 0;
    const age = now - ts;
    if (age < DAY) grouped.today.push(item);
    else if (age < WEEK) grouped.week.push(item);
    else grouped.older.push(item);
  });

  const hasAny = filtered.length > 0;

  const NAV_ICONS = [
    { id: 'audit',      icon: Shield,   label: 'Audit' },
    { id: 'evidence',   icon: FileText, label: 'Evidence' },
    { id: 'provenance', icon: GitFork,  label: 'Provenance' },
    { id: 'history',    icon: Clock,    label: 'History' },
  ];

  return (
    <aside className="history-sidebar" aria-label="Audit history sidebar">
      {/* ─── Left icon strip ─── */}
      <div className="sidebar-icon-strip">
        {/* Logo */}
        <div className="strip-logo" aria-label="Veritas">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="#0f766e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>

        {/* Nav icons */}
        <div className="strip-nav">
          {NAV_ICONS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              id={`rail-${id}`}
              className={`strip-btn ${activeView === id ? 'active' : ''}`}
              onClick={() => onNavigate(id)}
              aria-label={label}
              title={label}
            >
              <Icon size={17} strokeWidth={1.8} />
            </button>
          ))}
        </div>

        {/* Settings at bottom */}
        <div className="strip-bottom">
          <button
            id="rail-settings"
            className={`strip-btn ${activeView === 'settings' ? 'active' : ''}`}
            onClick={() => onNavigate('settings')}
            aria-label="Settings"
            title="Settings"
          >
            <Settings size={17} strokeWidth={1.8} />
          </button>
        </div>
      </div>

      {/* ─── History panel ─── */}
      <div className="sidebar-panel">
        {/* Panel header */}
        <div className="sidebar-panel-head">
          <span className="sidebar-panel-title">Recent audits</span>
          <button
            className="sidebar-search-btn"
            aria-label="Search audits"
            onClick={() => document.getElementById('sidebar-search')?.focus()}
          >
            <Search size={14} strokeWidth={1.8} color="var(--text-muted)" />
          </button>
        </div>

        {/* New Audit button */}
        <div style={{ padding: '0 12px 10px' }}>
          <button
            id="new-audit-btn"
            className="sidebar-new-btn"
            onClick={onNewAudit}
          >
            <Plus size={14} strokeWidth={2} />
            New audit
          </button>
        </div>

        {/* Search input */}
        <div className="sidebar-search-wrap">
          <Search size={12} strokeWidth={1.8} color="var(--text-muted)" />
          <input
            id="sidebar-search"
            className="sidebar-search-input"
            type="text"
            placeholder="Search audits…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search audit history"
          />
        </div>

        {/* History list */}
        <div className="sidebar-list" role="list">
          {!hasAny && !search && (
            <div className="sidebar-empty">
              <p className="sidebar-empty-title">No audits yet</p>
              <p className="sidebar-empty-sub">
                Submit your first claim above to start building your audit history.
              </p>
            </div>
          )}

          {!hasAny && search && (
            <div className="sidebar-empty">
              <p className="sidebar-empty-title">No results</p>
              <p className="sidebar-empty-sub">Try a different search term.</p>
            </div>
          )}

          {hasAny && (
            <>
              <HistoryGroup
                label="Today"
                items={grouped.today}
                activeJobId={activeJobId}
                onSelect={onSelectHistory}
              />
              <HistoryGroup
                label="This week"
                items={grouped.week}
                activeJobId={activeJobId}
                onSelect={onSelectHistory}
              />
              <HistoryGroup
                label="Older"
                items={grouped.older}
                activeJobId={activeJobId}
                onSelect={onSelectHistory}
              />
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

/**
 * HistoryGroup — collapsible section: "RECENTS", "THIS WEEK", "OLDER"
 */
function HistoryGroup({ label, items, activeJobId, onSelect }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!items.length) return null;

  return (
    <div className="history-group" role="group" aria-label={label}>
      <button
        className="history-group-label"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
      >
        <ChevronDown
          size={11}
          strokeWidth={2}
          style={{
            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
            color: 'var(--text-muted)',
          }}
        />
        <span>{label}</span>
      </button>

      {!collapsed && items.map((item) => (
        <HistoryItem
          key={item.job_id}
          item={item}
          isActive={item.job_id === activeJobId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

/**
 * HistoryItem — dot + truncated claim + verdict word (muted, right)
 */
function HistoryItem({ item, isActive, onSelect }) {
  const verdict = item.result?.verdict;
  const claim = item.result?.claim || 'Unknown claim';
  const cls = verdictClass(verdict);
  const label = verdictLabel(verdict).replace('.', '');

  return (
    <button
      className={`history-item ${isActive ? 'active' : ''}`}
      onClick={() => onSelect(item)}
      aria-label={`Audit: ${claim.slice(0, 60)} — ${label}`}
      role="listitem"
      title={claim}
    >
      <VerdictDot verdict={verdict} size={7} />
      <span className="history-item-claim">
        {claim.length > 52 ? claim.slice(0, 52) + '…' : claim}
      </span>
      <span
        className="history-item-verdict"
        style={{ color: `var(--verdict-${cls})` }}
      >
        {label}
      </span>
    </button>
  );
}
