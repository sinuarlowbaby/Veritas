import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, Send, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function FeedbackCard({ jobId, verdict, onFeedbackSubmitted }) {
  const [rating, setRating] = useState(null); // 'thumbs_up' or 'thumbs_down'
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);

  const quickTags = [
    'Solid evidence match',
    'Outdated article',
    'Quote out of context',
    'Fact-check consensus missed',
  ];

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!rating) return;

    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
          rating: rating,
          verdict: verdict || 'UNKNOWN',
          comment: comment.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      setSubmitted(true);
      if (onFeedbackSubmitted) {
        onFeedbackSubmitted(data);
      }
    } catch (err) {
      setError(err.message || 'Failed to submit feedback.');
    } finally {
      setSubmitting(false);
    }
  };

  const addQuickTag = (tag) => {
    setComment((prev) => (prev ? `${prev}; ${tag}` : tag));
  };

  if (submitted) {
    return (
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid #059669' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <CheckCircle2 size={20} color="#10b981" />
          <div>
            <h5 style={{ fontSize: '14px', fontWeight: '600', color: '#f1f5f9' }}>Feedback Recorded</h5>
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>
              Logged for regression evaluation harness and auditing.
            </p>
          </div>
        </div>
        <button
          onClick={() => setSubmitted(false)}
          style={{ fontSize: '11px', color: '#38bdf8', background: 'transparent', textDecoration: 'underline' }}
        >
          Update
        </button>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '18px 22px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <div>
          <h4 style={{ fontSize: '14px', fontWeight: '700', color: '#f8fafc' }}>
            Is this verification accurate?
          </h4>
          <p style={{ fontSize: '12px', color: '#94a3b8' }}>
            Provide human feedback to flag anomalies or validate the evidence trail.
          </p>
        </div>

        {/* Thumbs Up / Down Button Toggles */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setRating('thumbs_up')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: rating === 'thumbs_up' ? '#065f46' : '#1e293b',
              color: rating === 'thumbs_up' ? '#ffffff' : '#cbd5e1',
              border: rating === 'thumbs_up' ? '1px solid #10b981' : '1px solid #334155',
              fontWeight: '600',
              fontSize: '13px',
            }}
          >
            <ThumbsUp size={16} color={rating === 'thumbs_up' ? '#34d399' : '#94a3b8'} />
            <span>Accurate</span>
          </button>

          <button
            type="button"
            onClick={() => setRating('thumbs_down')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              background: rating === 'thumbs_down' ? '#991b1b' : '#1e293b',
              color: rating === 'thumbs_down' ? '#ffffff' : '#cbd5e1',
              border: rating === 'thumbs_down' ? '1px solid #ef4444' : '1px solid #334155',
              fontWeight: '600',
              fontSize: '13px',
            }}
          >
            <ThumbsDown size={16} color={rating === 'thumbs_down' ? '#f87171' : '#94a3b8'} />
            <span>Flag Disputed</span>
          </button>
        </div>
      </div>

      {rating && (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Quick Tag Pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {quickTags.map((t, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => addQuickTag(t)}
                style={{
                  fontSize: '11px',
                  padding: '3px 8px',
                  background: 'rgba(30, 41, 59, 0.7)',
                  color: '#94a3b8',
                  borderRadius: '12px',
                  border: '1px solid #334155',
                }}
              >
                + {t}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <textarea
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={rating === 'thumbs_down' ? 'Why was this verdict flagged? (e.g. source context was missed)' : 'Optional comments...'}
              style={{
                flex: 1,
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                color: '#f8fafc',
                padding: '8px 12px',
                fontSize: '13px',
                resize: 'none',
              }}
            />
            <button
              type="submit"
              disabled={submitting}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                padding: '0 18px',
                borderRadius: '8px',
                background: rating === 'thumbs_down' ? '#dc2626' : '#059669',
                color: '#ffffff',
                fontWeight: '600',
                fontSize: '13px',
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.7 : 1,
              }}
            >
              <Send size={14} />
              <span>{submitting ? 'Saving...' : 'Submit'}</span>
            </button>
          </div>

          {error && (
            <div style={{ color: '#ef4444', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={14} />
              <span>{error}</span>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
