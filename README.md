---
title: "Veritas — A Multi-Agent Debate System for Fake News Verification"
subtitle: "Project Proposal & System Design Document"
author: "Prepared for guide review"
date: "October 2026"
---

# 1. Abstract

Misinformation spreads faster than verified truth, and existing AI fact-checking tools suffer from a critical flaw: they rely on a _single_ Large Language Model (LLM) call, which can hallucinate citations, misjudge source credibility, and force a verdict even when evidence is insufficient. **Veritas** is a multi-agent verification system in which specialized agents debate a claim using live web evidence and curated fact-checking databases, and a judge agent produces a verdict that is _explainable, source-weighted, and willing to abstain_. The system decomposes claims into atomic sub-claims, requires verbatim quoted evidence with URLs, scores source credibility by tier, applies Natural Language Inference (NLI) verification to every piece of evidence, and maintains a human feedback loop with a regression evaluation harness. An evaluation benchmark of 100+ claims with ground truth is included to quantify precision, recall, hallucinated-citation rate, and verdict agreement with professional fact-checkers.

# 2. Introduction

## 2.1 Problem Statement

Manual fact-checking cannot keep pace with the volume of misinformation generated daily. Automated tools exist, but most are single-prompt LLM wrappers with no guarantees of evidence quality. We need a verification system that is **adversarial by design** (evidence for _and_ against is actively sought), **evidence-grounded** (every claim of fact is backed by a verifiable quote and URL), and **calibrated** (it reports confidence and abstains when evidence is thin).

## 2.2 Motivation

A debate structure mirrors the real journalistic process: a claim is strongest when it has survived a genuine attempt to refute it. Multi-agent orchestration allows each agent to have a narrow, well-defined role with dedicated tools and prompts, instead of one overloaded model doing everything.

## 2.3 Gap in Existing Work

Most student/demo "multi-agent" systems are **orchestration theater** — agents converse in natural language, but the final answer is still one LLM's unverified opinion. Veritas closes this gap with four mechanisms:

1. **Claim decomposition** — verdicts are computed per atomic sub-claim, then aggregated, instead of debating a whole headline at once.
2. **Cite-or-it-didn't-happen** — evidence without a verbatim quote + URL is discarded.
3. **Deterministic evidence labelling** — NLI cross-encoder labels each evidence item SUPPORTS / REFUTES / NEUTRAL; the Judge scores labels, not vibes.
4. **Abstention** — the system outputs _Unverified_ when evidence is thin, instead of hallucinating certainty.

# 3. Objectives

1. Build a multi-agent pipeline (LangGraph) that verifies any user-supplied headline, URL, or claim.
2. Guarantee evidence quality: every argument carries a verbatim quote, source URL, publication date, and source-tier score.
3. Produce calibrated verdicts: True / False / Partially True / Unverified, with a confidence score.
4. Provide full provenance: the user can click from the verdict down to every quote and source behind it.
5. Quantify system quality with a ground-truth evaluation benchmark and track regressions as the system evolves.

# 4. Scope

**In scope:** English-language factual claims, with a focused domain corpus of Indian political and health misinformation (viral WhatsApp-style claims, forwarded headlines); web + curated fact-check corpus as evidence; verdict explanation UI; feedback collection; evaluation harness.

**Out of scope (future work):** multilingual verification, image/video deepfake detection, real-time social-media stream monitoring.

Focusing on one domain with a curated benchmark makes the system credible rather than generically weak.

# 5. Proposed System

## 5.1 High-Level Architecture

![System Architecture](architecture_diagram.png)

## 5.2 Agents and Responsibilities

**Agent 0 — Claim Decomposer.** Takes raw input (headline/URL text) and splits it into atomic, independently checkable sub-claims. For example, a headline claiming "_The government announced policy X on date Y, projected to save Rs Z crores_" becomes three sub-claims: (i) policy X was announced, (ii) announcement date is Y, (iii) projected saving is Z crores. Aggregation logic maps sub-claim verdicts to a final verdict.

**Agent 1 — Proponent.** Actively searches for evidence _supporting_ each sub-claim using the live web search tool and the curated RAG corpus. Hard constraint: every returned item must contain a verbatim quote, source URL, and date. Items failing this are discarded.

**Agent 2 — Skeptic.** Identical tooling, opposite goal: find the strongest refuting evidence. The Skeptic is instructed to prefer primary sources (official records, full transcripts) over opinion pieces.

**NLI Verifier (deterministic component, not an LLM).** A cross-encoder NLI model labels every (sub-claim, evidence quote) pair as SUPPORTS / REFUTES / NEUTRAL. This converts free-text arguments into labelled facts that the Judge can weight objectively.

**Agent 3 — Judge.** Weighs labelled evidence by source tier and recency, computes a verdict per sub-claim with confidence, aggregates to a final verdict, and **abstains** (Unverified) when the weighted evidence mass on both sides falls below a threshold. The Judge never invents evidence — it can only score what is in the Evidence Store.

## 5.3 Source Credibility Tiers

| Tier | Examples                                                              | Weight |
| ---- | --------------------------------------------------------------------- | ------ |
| T1   | Government records, Reuters, AP, primary documents                    | 1.0    |
| T2   | Established news outlets, IFCN fact-checkers (Alt News, Boom, Snopes) | 0.75   |
| T3   | Aggregators, minor outlets with editorial standards                   | 0.5    |
| T4   | Blogs, forums, unattributed forwards                                  | 0.25   |

Weights are configurable and validated on the benchmark; they are a stated system parameter, not a hidden LLM behavior.

## 5.4 Evidence Store Schema

Every evidence item is stored in Postgres as:

```
evidence_id, sub_claim_id, quote (verbatim), source_url, domain,
domain_tier, publish_date, retrieved_date, nli_label,
nli_confidence, retrieved_by (proponent/skeptic), curated (bool)
```

This schema is what makes the system auditable and the provenance graph possible.

## 5.5 Judge Scoring Logic (summary)

For each sub-claim, score = Σ(weight_tier × nli_confidence) over supporting items minus the same over refuting items, with a recency decay factor. Verdict per sub-claim by thresholded score; overall verdict by aggregation rules (e.g., any core sub-claim refuted with high confidence → False). If |score| < abstention threshold and evidence count < minimum → **Unverified**.

# 6. Key Features

1. **Atomic claim decomposition** — composite headlines are verified piece by piece, making verdicts defensible.
2. **Adversarial retrieval** — dedicated Proponent and Skeptic agents search for and against, reducing confirmation bias.
3. **Cite-or-it-didn't-happen** — unquoted, unlinked evidence is rejected at the pipeline level.
4. **Source credibility weighting** — tiered, transparent source scoring; curated fact-check corpus outranks live web.
5. **NLI-based contradiction detection** — deterministic SUPPORTS/REFUTES/NEUTRAL labelling of every quote.
6. **Curated fact-check RAG** — vector store (pgvector) over Snopes, Alt News, Boom, IFCN signatories, and Wikipedia, refreshed periodically.
7. **Calibrated verdicts with abstention** — confidence score; "Unverified" when evidence is thin. Refusing to answer is a designed feature, not a failure.
8. **Evidence provenance graph** — interactive UI graph: verdict → sub-claims → evidence → sources. Users can audit every step.
9. **Freshness handling** — evidence carries temporal context; the system detects verdicts that were true once but became outdated (e.g., policy changed).
10. **Human feedback loop (LLMOps)** — users flag incorrect verdicts; feedback is stored and re-run as a regression suite whenever prompts, models, or weights change.
11. **Evaluation benchmark** — 100+ claims with ground truth spanning true / false / partially true / satire / outdated; metrics include per-class precision & recall, hallucinated-citation rate, and agreement with professional fact-checkers.
12. **Cost & latency tracking** — per-request token usage and latency logged, enabling engineering trade-off analysis (e.g., local Ollama vs OpenAI).

# 7. Workflow (End-to-End)

1. User submits a headline, URL, or free-text claim via the web UI (or browser extension).
2. Agent 0 decomposes it into atomic sub-claims.
3. For each sub-claim, Proponent and Skeptic run in parallel (LangGraph): live web search + curated RAG retrieval, emitting quote-URL pairs.
4. Sanitizer discards evidence missing quotes/URLs; deduplicates by domain.
5. NLI Verifier labels each surviving (sub-claim, quote) pair.
6. Everything is persisted to the Evidence Store.
7. Agent 3 scores the labelled evidence per source tier and recency, verdicts each sub-claim, aggregates, and abstains if evidence is thin.
8. UI renders verdict, confidence, and the provenance graph.
9. User feedback is stored; nightly job re-runs flagged claims and the regression eval suite.

# 8. Tech Stack

| Layer               | Choice                                                                    |
| ------------------- | ------------------------------------------------------------------------- |
| Agent orchestration | LangGraph (Python)                                                        |
| LLM                 | OpenAI API (primary) / Ollama Llama 3 (local fallback)                    |
| Web search          | Tavily API (primary), DuckDuckGo (fallback)                               |
| NLI                 | Cross-encoder NLI (e.g., `cross-encoder/nli-*`)                           |
| Database            | PostgreSQL + pgvector                                                     |
| Backend API         | FastAPI                                                                   |
| Frontend            | React + graph visualization (D3/Cytoscape)                                |
| Caching / queue     | Redis + Celery (for async verification jobs)                              |
| MLOps               | Docker, GitHub Actions CI, eval harness in pytest, Langfuse (LLM tracing) |

# 9. Getting Started & Running Instructions

### 9.1 Prerequisites

- **Python**: Version 3.11 or higher
- **OpenAI API Key**: Required for claim decomposition and LLM agents
- **Langfuse API Credentials** *(Optional)*: For LLM tracing and observability

---

### 9.2 Environment Configuration

1. Clone or navigate to the repository directory.
2. Create a `.env` file from `.env.example`:

   **PowerShell (Windows):**
   ```powershell
   Copy-Item .env.example .env
   ```

   **Bash (Linux / macOS):**
   ```bash
   cp .env.example .env
   ```

3. Open `.env` and configure your API keys:
   ```env
   # Required for Claim Decomposer and agents
   OPENAI_API_KEY=your_openai_api_key_here

   # Optional Langfuse Observability
   LANGFUSE_PUBLIC_KEY=your_public_key
   LANGFUSE_SECRET_KEY=your_secret_key
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

---

### 9.3 Environment Setup & Dependency Installation

1. Create a Python virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```

3. Install dependencies in editable mode:
   ```bash
   pip install -e backend
   ```
   *(To also install testing dependencies like pytest, run `pip install -e "backend[dev]"`)*

---

### 9.4 Running the Application

Start the FastAPI application with Uvicorn:

**Option 1: From the `backend` directory (Standard)**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Option 2: From the repository root**
```bash
python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

**Option 3: Directly via the main script**
```bash
python backend/app/main.py
```

Once running, the API server will be available at:
- **Base URL:** `http://localhost:8000`
- **Health Check:** `http://localhost:8000/health`
- **Interactive Swagger Docs (OpenAPI):** `http://localhost:8000/docs`
- **Alternative ReDoc UI:** `http://localhost:8000/redoc`

---

### 9.5 Testing the Endpoints

#### 1. Verify Service Health
```bash
curl http://localhost:8000/health
```
*Expected response:* `{"status":"ok","service":"veritas-api","version":"0.1.0"}`

#### 2. Test Claim Decomposer Endpoint (`POST /api/decompose`)

**cURL (Linux / macOS / Git Bash):**
```bash
curl -X POST "http://localhost:8000/api/decompose" \
  -H "Content-Type: application/json" \
  -d '{"text": "Finance Ministry eliminates all income tax for citizens over 60 starting April 1, causing Rs 40,000 crore revenue loss"}'
```

**PowerShell (Windows):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/decompose" `
  -Method Post `
  -Headers @{"Content-Type" = "application/json"} `
  -Body '{"text": "Finance Ministry eliminates all income tax for citizens over 60 starting April 1, causing Rs 40,000 crore revenue loss"}' | ConvertTo-Json -Depth 5
```

---

### 9.6 Running the Test Suite

Execute the Claim Decomposer isolation test suite to verify end-to-end decomposition with sample composite claims:

```bash
python backend/tests/test_decomposer.py
```

Or run tests with `pytest`:
```bash
pytest backend/tests
```

# 10. Evaluation Plan

**Benchmark construction.** 100–150 claims with verified ground truth: mix of true, false, partially true, satire, and outdated claims; ~60% from the focused domain (Indian political/health misinformation), 40% general. Sources for ground truth: IFCN signatory verdicts, official records.

**Metrics.**

- Per-class precision, recall, F1 for True / False / Partially True / Unverified
- Hallucinated-citation rate (fraction of verdicts citing a quote that does not exist or does not say what is claimed)
- Verdict agreement rate with professional fact-checkers
- Abstention correctness (Unverified raised when fact-checkers also found evidence thin)
- Latency and cost per verification

**Regression harness.** Every prompt change, model swap, or tier-weight change must re-run the benchmark; results are versioned and compared.

# 11. Project Timeline (14 weeks)

| Weeks | Milestone                                                                      |
| ----- | ------------------------------------------------------------------------------ |
| 1–2   | Literature review, benchmark dataset v1 (50 claims), architecture finalization |
| 3–4   | Claim Decomposer + web search tools + Evidence Store schema                    |
| 5–6   | Proponent/Skeptic agents, cite validation, curated RAG ingestion               |
| 7     | NLI Verifier integration                                                       |
| 8–9   | Judge scoring + abstention + aggregation                                       |
| 10    | UI: verdict page + provenance graph                                            |
| 11    | Feedback loop + regression harness                                             |
| 12    | Benchmark scale-up to 100+, metrics report                                     |
| 13    | End-to-end hardening, Docker, CI/CD, deployment                                |
| 14    | Documentation, demo video, guide review                                        |

# 12. Expected Outcomes & Impact

- A working system that matches or exceeds professional fact-checker agreement on the benchmark subset, while being fully auditable.
- Demonstrated ability to say "I don't know" — a property most Gen AI systems lack.
- Reusable components: claim decomposition module, evidence store schema, and the regression harness are applicable to any RAG/agent system.

# 13. Future Scope

Multilingual claim verification; multimodal evidence (images, WhatsApp forwards screenshots via OCR); browser extension for one-click checks; continuous social-stream monitoring; reinforcement learning from human feedback on judge weighting.

# 14. Conclusion

Veritas treats fake-news verification as an _evidence engineering_ problem rather than a prompting problem. By combining adversarial multi-agent retrieval, deterministic NLI labelling, source-tier weighting, abstention, and a rigorous evaluation benchmark, it converts a demo-grade idea into a production-grade, interview-defensible system where every verdict is traceable to a quoted source.
