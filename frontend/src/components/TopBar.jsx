import React from 'react';

/**
 * TopBar — 52px fixed top bar.
 * Left: serif wordmark "Veritas"
 * Right: green dot + "pipeline healthy" + muted job id
 */
export default function TopBar({ jobId, pipelineStatus = 'healthy' }) {
  const isHealthy = pipelineStatus === 'healthy';

  return (
    <header className="topbar" role="banner">
      {/* Wordmark */}
      <span className="topbar-wordmark" aria-label="Veritas">
        Veritas
      </span>

      {/* Status + job id */}
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
      </div>
    </header>
  );
}
