import React from 'react';
import { Shield, FileText, GitFork, Clock, Settings } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'audit',      icon: Shield,    label: 'Audit' },
  { id: 'evidence',   icon: FileText,  label: 'Evidence' },
  { id: 'provenance', icon: GitFork,   label: 'Provenance' },
  { id: 'history',    icon: Clock,     label: 'History' },
];

/**
 * IconRail — 58px fixed left rail with SVG line icons.
 * Active item: teal background + 3px teal indicator bar on left.
 * No labels, no colored text except active item (teal).
 */
export default function IconRail({ activeView, onNavigate }) {
  return (
    <nav className="icon-rail" role="navigation" aria-label="Main navigation">
      {/* Logo mark */}
      <div className="rail-logo" aria-label="Veritas">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0f766e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      </div>

      {/* Nav items */}
      {NAV_ITEMS.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          id={`nav-${id}`}
          className={`rail-nav-item ${activeView === id ? 'active' : ''}`}
          onClick={() => onNavigate(id)}
          aria-label={label}
          aria-current={activeView === id ? 'page' : undefined}
          title={label}
        >
          <Icon size={18} strokeWidth={1.8} />
          <span className="rail-tooltip">{label}</span>
        </button>
      ))}

      <div className="rail-spacer" />

      {/* Settings at bottom */}
      <button
        id="nav-settings"
        className={`rail-nav-item ${activeView === 'settings' ? 'active' : ''}`}
        onClick={() => onNavigate('settings')}
        aria-label="Settings"
        title="Settings"
      >
        <Settings size={18} strokeWidth={1.8} />
        <span className="rail-tooltip">Settings</span>
      </button>
    </nav>
  );
}
