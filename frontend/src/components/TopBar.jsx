import React from 'react';

/**
 * TopBar — 52px fixed top bar.
 * Left: serif wordmark "Veritas"
 * Right: pipeline health + job id + user authentication button/pill
 */
export default function TopBar({
  jobId,
  pipelineStatus = 'healthy',
  user = null,
  onOpenAuth = () => {},
  onLogout = () => {},
}) {
  const isHealthy = pipelineStatus === 'healthy';

  return (
    <header className="topbar" role="banner">
      {/* Wordmark */}
      <span className="topbar-wordmark" aria-label="Veritas">
        Veritas
      </span>

      {/* Right section: status, job, auth */}
      <div className="topbar-status">
        <span
          className="topbar-status-dot"
          style={{ background: isHealthy ? '#16a34a' : '#d97706' }}
          aria-hidden="true"
        />
        <span>pipeline {isHealthy ? 'healthy' : 'degraded'}</span>

        {jobId && (
          <span className="topbar-job" aria-label={`Job ID: ${jobId}`}>
            {jobId}
          </span>
        )}

        {/* User Account / Auth Actions */}
        <div className="topbar-auth">
          {user ? (
            <div className="topbar-user-pill">
              <span className="topbar-avatar" title={`Logged in as ${user.username}`}>
                {user.username.charAt(0).toUpperCase()}
              </span>
              <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
                {user.username}
              </span>
              <button
                className="topbar-sign-out-btn"
                onClick={onLogout}
                aria-label="Sign out"
                title="Sign out of your account"
              >
                Sign out
              </button>
            </div>
          ) : (
            <button
              className="topbar-sign-in-btn"
              onClick={onOpenAuth}
              aria-label="Sign in to save audits across devices"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
