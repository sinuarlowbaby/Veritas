import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';

/**
 * FeedbackRow — Quiet footer below audit results.
 * "Was this audit accurate?" + two ghost icon buttons (thumbs up/down).
 * No filled colors, no banners — just hairline border-top.
 */
export default function FeedbackRow({ jobId, verdict, onFeedbackSubmitted }) {
  const [selected, setSelected] = useState(null); // 'up' | 'down' | null
  const [submitted, setSubmitted] = useState(false);

  const handleFeedback = async (type) => {
    if (submitted) return;
    setSelected(type);
    setSubmitted(true);

    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, verdict, feedback: type }),
      });
    } catch {
      // Silently fail — feedback is non-critical
    }

    onFeedbackSubmitted?.({ job_id: jobId, feedback: type });
  };

  return (
    <div className="feedback-row" aria-label="Feedback on audit accuracy">
      <span className="feedback-label">
        {submitted
          ? selected === 'up'
            ? 'Thanks — marked as accurate.'
            : 'Thanks — we\'ll review this.'
          : 'Was this audit accurate?'}
      </span>

      <button
        id="feedback-thumbs-up"
        className={`feedback-btn ${selected === 'up' ? 'selected' : ''}`}
        onClick={() => handleFeedback('up')}
        disabled={submitted}
        aria-label="Mark audit as accurate"
        aria-pressed={selected === 'up'}
      >
        <ThumbsUp size={14} strokeWidth={1.8} />
      </button>

      <button
        id="feedback-thumbs-down"
        className={`feedback-btn ${selected === 'down' ? 'selected' : ''}`}
        onClick={() => handleFeedback('down')}
        disabled={submitted}
        aria-label="Mark audit as inaccurate"
        aria-pressed={selected === 'down'}
      >
        <ThumbsDown size={14} strokeWidth={1.8} />
      </button>
    </div>
  );
}
