import React from 'react';
import { verdictClass } from './VerdictDot';

/**
 * ProvenanceGraph — Minimal SVG node-link diagram.
 * One top node (verdict), middle nodes (sub-claims), bottom dots (sources).
 * Thin gray lines, labels in tiny italic serif. Airy, centered.
 * No cytoscape dependency needed for this minimal editorial view.
 */
export default function ProvenanceGraph({ result }) {
  if (!result) {
    return (
      <div className="view-container">
        <h2 className="view-title">Provenance</h2>
        <p className="view-subtitle" style={{ marginBottom: 0 }}>
          Submit a claim to visualise source provenance.
        </p>
      </div>
    );
  }

  const { verdict, sub_claims = [], evidence = [] } = result;
  const verdictCls = verdictClass(verdict);

  const DOT_COLORS = {
    true: '#16a34a',
    false: '#dc2626',
    mixed: '#d97706',
    unverified: '#a8a29e',
  };

  // Layout constants
  const W = 640;
  const H = 380;
  const CX = W / 2;

  // Top node (verdict)
  const topNode = { x: CX, y: 60, r: 18 };

  // Mid nodes (sub-claims), spread evenly
  const midCount = Math.min(sub_claims.length, 4);
  const midSpread = Math.min(480, midCount * 140);
  const midNodes = Array.from({ length: midCount }, (_, i) => ({
    x: CX - midSpread / 2 + (midCount === 1 ? midSpread / 2 : (midSpread / (midCount - 1)) * i),
    y: 180,
    r: 12,
    sc: sub_claims[i],
  }));

  // Bottom source dots (evidence grouped by sub-claim)
  const bottomNodes = [];
  midNodes.forEach((mid, mi) => {
    const subEv = evidence.filter((e) => e.sub_claim_id === mid.sc?.id).slice(0, 3);
    subEv.forEach((ev, ei) => {
      const spread = (subEv.length - 1) * 36;
      bottomNodes.push({
        x: mid.x - spread / 2 + ei * 36,
        y: 310,
        r: 5,
        ev,
        midIdx: mi,
      });
    });
  });

  return (
    <div className="view-container">
      <h2 className="view-title">Provenance</h2>
      <p className="view-subtitle">
        Source lineage from claim to evidence
      </p>

      <div className="provenance-panel">
        <svg
          className="prov-graph-svg"
          viewBox={`0 0 ${W} ${H}`}
          aria-label="Provenance graph showing claim, sub-claims, and sources"
          role="img"
        >
          {/* Lines: top → mid */}
          {midNodes.map((mid, i) => (
            <line
              key={`tm-${i}`}
              x1={topNode.x} y1={topNode.y + topNode.r}
              x2={mid.x} y2={mid.y - mid.r}
              stroke="#d6d3d1" strokeWidth="1"
            />
          ))}

          {/* Lines: mid → bottom */}
          {bottomNodes.map((bot, i) => {
            const mid = midNodes[bot.midIdx];
            return (
              <line
                key={`mb-${i}`}
                x1={mid.x} y1={mid.y + mid.r}
                x2={bot.x} y2={bot.y - bot.r}
                stroke="#e7e5e4" strokeWidth="1"
              />
            );
          })}

          {/* Top verdict node — pastel circle fill */}
          <circle
            cx={topNode.x} cy={topNode.y} r={topNode.r}
            fill={DOT_COLORS[verdictCls] + '22'}
            stroke={DOT_COLORS[verdictCls]}
            strokeWidth="1.5"
          />
          <text
            x={topNode.x} y={topNode.y + 4}
            textAnchor="middle"
            fontSize="9"
            fontFamily="Lora, Georgia, serif"
            fontStyle="italic"
            fill={DOT_COLORS[verdictCls]}
          >
            {verdict?.toLowerCase() || 'unverified'}
          </text>

          {/* Top label */}
          <text
            x={topNode.x} y={topNode.y - topNode.r - 8}
            textAnchor="middle"
            fontSize="9.5"
            fontFamily="Lora, Georgia, serif"
            fontStyle="italic"
            fill="#a8a29e"
          >
            verdict
          </text>

          {/* Mid sub-claim nodes — outlined circles */}
          {midNodes.map((mid, i) => {
            const sc = mid.sc;
            const scCls = verdictClass(sc?.verdict);
            const scColor = DOT_COLORS[scCls];
            const label = sc?.text
              ? sc.text.length > 22
                ? sc.text.slice(0, 22) + '…'
                : sc.text
              : `sub-claim ${i + 1}`;

            return (
              <g key={`mid-${i}`}>
                <circle
                  cx={mid.x} cy={mid.y} r={mid.r}
                  fill="white"
                  stroke={scColor}
                  strokeWidth="1.5"
                />
                <circle cx={mid.x} cy={mid.y} r={4} fill={scColor} />
                <text
                  x={mid.x} y={mid.y + mid.r + 14}
                  textAnchor="middle"
                  fontSize="8.5"
                  fontFamily="Lora, Georgia, serif"
                  fontStyle="italic"
                  fill="#78716c"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* Bottom source dots */}
          {bottomNodes.map((bot, i) => {
            const cls = bot.ev.nli_label === 'REFUTES' ? 'false'
              : bot.ev.nli_label === 'SUPPORTS' ? 'true' : 'mixed';
            const col = DOT_COLORS[cls];
            const domain = bot.ev.domain
              || (() => { try { return new URL(bot.ev.source_url || '').hostname.replace('www.', ''); } catch { return '?'; } })();
            const shortDomain = domain.length > 12 ? domain.slice(0, 12) + '…' : domain;

            return (
              <g key={`bot-${i}`}>
                <circle
                  cx={bot.x} cy={bot.y} r={bot.r}
                  fill={col}
                />
                <text
                  x={bot.x} y={bot.y + bot.r + 11}
                  textAnchor="middle"
                  fontSize="7.5"
                  fontFamily="Lora, Georgia, serif"
                  fontStyle="italic"
                  fill="#a8a29e"
                >
                  {shortDomain}
                </text>
              </g>
            );
          })}

          {/* Legend */}
          <g transform={`translate(${W - 120}, ${H - 40})`}>
            {[
              { color: DOT_COLORS.true, label: 'supports' },
              { color: DOT_COLORS.false, label: 'refutes' },
              { color: DOT_COLORS.mixed, label: 'neutral' },
            ].map((item, i) => (
              <g key={item.label} transform={`translate(0, ${i * 14})`}>
                <circle cx={5} cy={4} r={4} fill={item.color} />
                <text x={14} y={8} fontSize="8" fontFamily="Lora, Georgia, serif" fontStyle="italic" fill="#a8a29e">
                  {item.label}
                </text>
              </g>
            ))}
          </g>
        </svg>
      </div>
    </div>
  );
}
