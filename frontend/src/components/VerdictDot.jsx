import React from 'react';

/**
 * VerdictDot — 7-8px colored dot, NO pill badges, NO background blocks.
 * Color appears ONLY as this small dot + matching text color.
 */
export function VerdictDot({ verdict, size = 8 }) {
  const cls = verdictClass(verdict);
  return (
    <span
      className={`verdict-dot ${cls}`}
      style={{ width: size, height: size }}
      aria-label={`Verdict: ${verdict}`}
    />
  );
}

/**
 * Returns a CSS class key from verdict string
 */
export function verdictClass(verdict) {
  if (!verdict) return 'unverified';
  const v = verdict.toUpperCase();
  if (v === 'TRUE' || v === 'SUPPORTED') return 'true';
  if (v === 'FALSE' || v === 'REFUTES') return 'false';
  if (v === 'MIXED' || v === 'PARTIALLY_TRUE') return 'mixed';
  return 'unverified';
}

/**
 * Returns human-readable label for verdict
 */
export function verdictLabel(verdict) {
  if (!verdict) return 'Unverified';
  const v = verdict.toUpperCase();
  if (v === 'TRUE' || v === 'SUPPORTED') return 'Verified true.';
  if (v === 'FALSE' || v === 'REFUTES') return 'False.';
  if (v === 'MIXED' || v === 'PARTIALLY_TRUE') return 'Mixed.';
  return 'Unverified.';
}

/**
 * NLI dot for evidence — maps SUPPORTS/REFUTES/NEUTRAL to dot class
 */
export function nliClass(label) {
  if (!label) return 'unverified';
  const l = label.toUpperCase();
  if (l === 'SUPPORTS' || l === 'SUPPORTED') return 'true';
  if (l === 'REFUTES' || l === 'REFUTED') return 'false';
  return 'mixed';
}

export function nliLabel(label) {
  if (!label) return 'Neutral';
  const l = label.toUpperCase();
  if (l === 'SUPPORTS' || l === 'SUPPORTED') return 'Supports';
  if (l === 'REFUTES' || l === 'REFUTED') return 'Refutes';
  return 'Neutral';
}

export default VerdictDot;
