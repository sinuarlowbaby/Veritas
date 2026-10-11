import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Filter, Layers, ExternalLink } from 'lucide-react';

// Register dagre layout once
try {
  cytoscape.use(dagre);
} catch (e) {
  // Already registered
}

export default function ProvenanceGraph({ result, onSelectNode, selectedNodeId }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [filterNli, setFilterNli] = useState('ALL'); // ALL, SUPPORTS, REFUTES, NEUTRAL

  useEffect(() => {
    if (!containerRef.current || !result) return;

    // Build Cytoscape Elements from verification result JSON
    const elements = [];

    // 1. Root Verdict Node
    const verdict = result.verdict || 'UNVERIFIED';
    const confidencePct = Math.round((result.confidence || 0) * 100);
    const rootNodeId = 'verdict_root';

    elements.push({
      data: {
        id: rootNodeId,
        label: `${verdict}\n(${confidencePct}% Conf)`,
        type: 'verdict',
        verdict: verdict,
        score: result.score,
        confidence: result.confidence,
        claim: result.claim,
        explanation: result.explanation,
        key_citations: result.key_citations || [],
      },
    });

    // 2. Sub-claim Nodes (Middle Level)
    const subClaims = result.sub_claims || [];
    subClaims.forEach((sc) => {
      elements.push({
        data: {
          id: sc.id,
          label: `${sc.text.length > 55 ? sc.text.substring(0, 52) + '...' : sc.text}\n[${sc.verdict}]`,
          fullText: sc.text,
          type: 'subclaim',
          verdict: sc.verdict,
          score: sc.score,
          confidence: sc.confidence,
          evidence_count: sc.evidence_count,
          supporting_count: sc.supporting_count,
          refuting_count: sc.refuting_count,
          neutral_count: sc.neutral_count,
        },
      });

      // Edge: Verdict -> Sub-claim
      elements.push({
        data: {
          id: `edge_root_${sc.id}`,
          source: rootNodeId,
          target: sc.id,
          type: 'verdict_to_subclaim',
          verdict: sc.verdict,
        },
      });
    });

    // 3. Evidence Nodes (Bottom Level)
    const evidenceList = result.evidence || [];
    evidenceList.forEach((ev) => {
      const nliLabel = (ev.nli_label || 'NEUTRAL').toUpperCase();
      
      // Filter check
      if (filterNli !== 'ALL' && nliLabel !== filterNli) {
        return;
      }

      const confPct = Math.round((ev.nli_confidence || 0) * 100);
      const tierLabel = `T${ev.domain_tier || 4}`;
      const domainName = ev.domain || 'web source';

      elements.push({
        data: {
          id: ev.evidence_id,
          label: `${domainName} [${tierLabel}]\n${nliLabel} (${confPct}%)`,
          type: 'evidence',
          sub_claim_id: ev.sub_claim_id,
          sub_claim: ev.sub_claim,
          quote: ev.quote,
          source_url: ev.source_url,
          domain: ev.domain,
          domain_tier: ev.domain_tier || 4,
          nli_label: nliLabel,
          nli_confidence: ev.nli_confidence,
          retrieved_by: ev.retrieved_by,
        },
      });

      // Edge: Sub-claim -> Evidence
      elements.push({
        data: {
          id: `edge_${ev.sub_claim_id}_${ev.evidence_id}`,
          source: ev.sub_claim_id,
          target: ev.evidence_id,
          type: 'subclaim_to_evidence',
          nli_label: nliLabel,
        },
      });
    });

    // Destroy existing instance before creating a new one
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    // Initialize Cytoscape Instance
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        // ------------------ Core Node Styles ------------------
        {
          selector: 'node',
          style: {
            'font-family': 'Inter, sans-serif',
            'font-size': '11px',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '190px',
            'color': '#f8fafc',
            'transition-property': 'background-color, border-color, border-width, box-shadow',
            'transition-duration': '0.2s',
          },
        },

        // ------------------ Verdict Root Node ------------------
        {
          selector: 'node[type = "verdict"]',
          style: {
            'shape': 'round-rectangle',
            'width': '220px',
            'height': '68px',
            'font-size': '13px',
            'font-weight': 'bold',
            'text-margin-y': 0,
            'border-width': '3px',
            'border-color': '#ffffff',
          },
        },
        {
          selector: 'node[type = "verdict"][verdict = "TRUE"]',
          style: {
            'background-color': '#059669',
            'border-color': '#34d399',
          },
        },
        {
          selector: 'node[type = "verdict"][verdict = "FALSE"]',
          style: {
            'background-color': '#dc2626',
            'border-color': '#f87171',
          },
        },
        {
          selector: 'node[type = "verdict"][verdict = "PARTIALLY TRUE"]',
          style: {
            'background-color': '#d97706',
            'border-color': '#fbbf24',
          },
        },
        {
          selector: 'node[type = "verdict"][verdict = "UNVERIFIED"]',
          style: {
            'background-color': '#475569',
            'border-color': '#94a3b8',
          },
        },

        // ------------------ Sub-claim Nodes ------------------
        {
          selector: 'node[type = "subclaim"]',
          style: {
            'shape': 'round-rectangle',
            'width': '230px',
            'height': '72px',
            'font-size': '10px',
            'line-height': 1.3,
            'border-width': '2px',
          },
        },
        {
          selector: 'node[type = "subclaim"][verdict = "TRUE"]',
          style: {
            'background-color': '#064e3b',
            'border-color': '#10b981',
          },
        },
        {
          selector: 'node[type = "subclaim"][verdict = "FALSE"]',
          style: {
            'background-color': '#7f1d1d',
            'border-color': '#ef4444',
          },
        },
        {
          selector: 'node[type = "subclaim"][verdict = "PARTIALLY TRUE"]',
          style: {
            'background-color': '#78350f',
            'border-color': '#f59e0b',
          },
        },
        {
          selector: 'node[type = "subclaim"][verdict = "UNVERIFIED"]',
          style: {
            'background-color': '#1e293b',
            'border-color': '#64748b',
          },
        },

        // ------------------ Evidence Nodes ------------------
        {
          selector: 'node[type = "evidence"]',
          style: {
            'shape': 'round-rectangle',
            'width': '180px',
            'height': '54px',
            'font-size': '10px',
            'font-weight': '500',
            'cursor': 'pointer',
          },
        },
        // NLI State Coloring
        {
          selector: 'node[type = "evidence"][nli_label = "SUPPORTS"]',
          style: {
            'background-color': '#065f46',
          },
        },
        {
          selector: 'node[type = "evidence"][nli_label = "REFUTES"]',
          style: {
            'background-color': '#991b1b',
          },
        },
        {
          selector: 'node[type = "evidence"][nli_label = "NEUTRAL"]',
          style: {
            'background-color': '#334155',
          },
        },
        // Source Tier Border Badging
        {
          selector: 'node[type = "evidence"][domain_tier = 1]',
          style: {
            'border-width': '4px',
            'border-color': '#eab308', // Gold - Academic / Official Fact-Checker
          },
        },
        {
          selector: 'node[type = "evidence"][domain_tier = 2]',
          style: {
            'border-width': '3px',
            'border-color': '#38bdf8', // Blue/Cyan - Major Government / Top News
          },
        },
        {
          selector: 'node[type = "evidence"][domain_tier = 3]',
          style: {
            'border-width': '2px',
            'border-color': '#c084fc', // Purple - Regional / Specialist
          },
        },
        {
          selector: 'node[type = "evidence"][domain_tier = 4]',
          style: {
            'border-width': '1.5px',
            'border-color': '#94a3b8', // Gray - Web / General
          },
        },

        // ------------------ Selected Node Highlight ------------------
        {
          selector: 'node:selected',
          style: {
            'border-color': '#ffffff',
            'border-width': '5px',
            'shadow-blur': 25,
            'shadow-color': '#38bdf8',
            'shadow-opacity': 0.8,
          },
        },

        // ------------------ Edge Styles ------------------
        {
          selector: 'edge',
          style: {
            'width': 2,
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.1,
            'opacity': 0.75,
          },
        },
        {
          selector: 'edge[type = "verdict_to_subclaim"]',
          style: {
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'width': 2.5,
          },
        },
        {
          selector: 'edge[type = "subclaim_to_evidence"][nli_label = "SUPPORTS"]',
          style: {
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
          },
        },
        {
          selector: 'edge[type = "subclaim_to_evidence"][nli_label = "REFUTES"]',
          style: {
            'line-color': '#ef4444',
            'target-arrow-color': '#ef4444',
          },
        },
        {
          selector: 'edge[type = "subclaim_to_evidence"][nli_label = "NEUTRAL"]',
          style: {
            'line-color': '#64748b',
            'target-arrow-color': '#64748b',
          },
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'TB', // Top to bottom 3 levels
        align: 'DL',
        rankSep: 90,
        nodeSep: 45,
        edgeSep: 25,
        animate: true,
        animationDuration: 400,
        fit: true,
        padding: 40,
      },
    });

    // Event Handlers
    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data();
      if (onSelectNode) {
        onSelectNode(nodeData);
      }
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        if (onSelectNode) {
          onSelectNode(null);
        }
      }
    });

    // Double tap on evidence opens source URL directly
    cy.on('dbltap', 'node[type = "evidence"]', (evt) => {
      const data = evt.target.data();
      if (data.source_url) {
        window.open(data.source_url, '_blank', 'noopener,noreferrer');
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [result, filterNli]);

  // Sync selected node highlight from prop
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;
    cy.nodes().unselect();
    if (selectedNodeId) {
      const target = cy.$(`#${selectedNodeId}`);
      if (target.length > 0) {
        target.select();
      }
    }
  }, [selectedNodeId]);

  const handleZoomIn = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.25);
  };

  const handleZoomOut = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 0.8);
  };

  const handleFit = () => {
    if (cyRef.current) cyRef.current.fit(undefined, 40);
  };

  const handleResetLayout = () => {
    if (cyRef.current) {
      cyRef.current.layout({
        name: 'dagre',
        rankDir: 'TB',
        rankSep: 90,
        nodeSep: 45,
        animate: true,
        animationDuration: 300,
        fit: true,
        padding: 40,
      }).run();
    }
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '520px', borderRadius: '12px', overflow: 'hidden', background: '#090d16', border: '1px solid #1f2e46' }}>
      {/* Top Floating Graph Toolbar */}
      <div style={{ position: 'absolute', top: '14px', right: '14px', zIndex: 10, display: 'flex', gap: '8px', background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(10px)', padding: '6px 10px', borderRadius: '8px', border: '1px solid #334155' }}>
        <button onClick={handleZoomIn} title="Zoom In" style={{ background: 'transparent', color: '#cbd5e1', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
          <ZoomIn size={16} />
        </button>
        <button onClick={handleZoomOut} title="Zoom Out" style={{ background: 'transparent', color: '#cbd5e1', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
          <ZoomOut size={16} />
        </button>
        <button onClick={handleFit} title="Fit to Screen" style={{ background: 'transparent', color: '#cbd5e1', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
          <Maximize2 size={16} />
        </button>
        <button onClick={handleResetLayout} title="Reset Layout" style={{ background: 'transparent', color: '#cbd5e1', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
          <RotateCcw size={16} />
        </button>
      </div>

      {/* Filter Toolbar (NLI State Filter) */}
      <div style={{ position: 'absolute', top: '14px', left: '14px', zIndex: 10, display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(10px)', padding: '5px 8px', borderRadius: '8px', border: '1px solid #334155' }}>
        <Filter size={14} color="#94a3b8" />
        <span style={{ fontSize: '11px', color: '#94a3b8', marginRight: '4px' }}>Filter:</span>
        {['ALL', 'SUPPORTS', 'REFUTES', 'NEUTRAL'].map((f) => (
          <button
            key={f}
            onClick={() => setFilterNli(f)}
            style={{
              padding: '3px 8px',
              fontSize: '11px',
              fontWeight: filterNli === f ? '600' : '400',
              borderRadius: '5px',
              background: filterNli === f ? (f === 'SUPPORTS' ? '#065f46' : f === 'REFUTES' ? '#991b1b' : f === 'NEUTRAL' ? '#334155' : '#1e293b') : 'transparent',
              color: filterNli === f ? '#ffffff' : '#94a3b8',
              border: filterNli === f ? '1px solid #475569' : '1px solid transparent',
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Bottom Graph Legend */}
      <div style={{ position: 'absolute', bottom: '12px', left: '14px', zIndex: 10, display: 'flex', flexWrap: 'wrap', gap: '14px', background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(8px)', padding: '6px 12px', borderRadius: '8px', border: '1px solid #1e293b', fontSize: '11px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#059669', display: 'inline-block' }}></span>
          <span style={{ color: '#cbd5e1' }}>Supports</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#dc2626', display: 'inline-block' }}></span>
          <span style={{ color: '#cbd5e1' }}>Refutes</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#475569', display: 'inline-block' }}></span>
          <span style={{ color: '#cbd5e1' }}>Neutral</span>
        </div>
        <div style={{ width: '1px', height: '14px', background: '#334155', margin: '0 2px' }}></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ border: '2px solid #eab308', width: '8px', height: '8px', borderRadius: '2px', display: 'inline-block' }}></span>
          <span style={{ color: '#eab308' }}>T1 Fact-check</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ border: '2px solid #38bdf8', width: '8px', height: '8px', borderRadius: '2px', display: 'inline-block' }}></span>
          <span style={{ color: '#38bdf8' }}>T2 Gov / Major</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ border: '1.5px solid #c084fc', width: '8px', height: '8px', borderRadius: '2px', display: 'inline-block' }}></span>
          <span style={{ color: '#c084fc' }}>T3 Specialist</span>
        </div>
      </div>

      {/* The Cytoscape Container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%', minHeight: '520px' }} />
    </div>
  );
}
