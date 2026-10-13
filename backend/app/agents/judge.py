import asyncio
from datetime import datetime, timezone
import logging
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load environment variables (.env from backend or root)
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

from app.models.schemas import (
    EvidenceItem,
    JudgeVerdictRequest,
    JudgeVerdictResponse,
    SubClaim,
    SubClaimVerdict,
)

logger = logging.getLogger("veritas.judge")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    from langfuse.openai import AsyncOpenAI
    logger.info("Langfuse tracking enabled for Judge Agent.")
else:
    from openai import AsyncOpenAI

    def observe(*args, **kwargs):
        """Pass-through decorator when Langfuse is not enabled."""
        def decorator(fn):
            return fn
        return decorator

    logger.info("Langfuse credentials not set; running Judge Agent with standard logging.")


# ---------------------------------------------------------------------------
# Part 1 Constants & Math Scoring Functions
# ---------------------------------------------------------------------------
# Source credibility tier weights as defined in Veritas architecture
TIER_WEIGHTS: Dict[int, float] = {
    1: 1.00,  # Tier 1: Curated IFCN fact-checkers (Alt News, Boom, Snopes, IFCN signatories)
    2: 0.75,  # Tier 2: Government agencies, official registries, multilateral bodies (WHO, PIB, ISRO)
    3: 0.50,  # Tier 3: Reputable mainstream journalism, peer-reviewed publications
    4: 0.25,  # Tier 4: General web search results, unverified publications, blog posts
}

# Freshness & Recency decay parameters
RECENT_DAYS_THRESHOLD = 365.0      # <= 1 year old: 100% weight
RECENCY_DECAY_1_YEAR = 0.85        # > 1 year old: 85% weight
RECENCY_DECAY_3_YEARS = 0.70       # > 3 years old: 70% weight
RECENCY_DECAY_UNDATED = 1.00       # Undated source: 100% weight (no arbitrary penalty if unlisted)

# Part 2 Decision Threshold Constants
TRUE_THRESHOLD = 0.45             # Calibrated positive threshold
FALSE_THRESHOLD = -0.30            # Calibrated refute threshold: allows credible counter-evidence to refute
ABSTENTION_SCORE_THRESHOLD = 0.20 # Calibrated abstention threshold: reduces excessive UNVERIFIED on real claims
MIN_EVIDENCE_COUNT = 1            # Single authoritative debunk or confirmation can decide
HIGH_CONFIDENCE_THRESHOLD = 0.60  # Calibrated high-confidence threshold


def calculate_recency_decay(
    publish_date_str: Optional[str],
    reference_date: Optional[datetime] = None,
) -> float:
    """
    Computes a recency discount factor based on source age.
    Older evidence is slightly discounted to reflect information freshness.
    """
    if not publish_date_str or not publish_date_str.strip():
        return RECENCY_DECAY_UNDATED

    ref_date = reference_date or datetime.now(timezone.utc)
    date_clean = publish_date_str.strip()[:10]  # Expect YYYY-MM-DD

    try:
        pub_dt = datetime.strptime(date_clean, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_old = (ref_date - pub_dt).total_seconds() / 86400.0

        if days_old <= RECENT_DAYS_THRESHOLD:
            return 1.00
        elif days_old <= RECENT_DAYS_THRESHOLD * 3.0:
            return RECENCY_DECAY_1_YEAR
        else:
            return RECENCY_DECAY_3_YEARS
    except Exception:
        return RECENCY_DECAY_UNDATED


def calculate_sub_claim_score(
    evidence_items: List[EvidenceItem],
    reference_date: Optional[datetime] = None,
) -> float:
    """
    Pure mathematical scoring function:
      score = sum(w_tier * nli_confidence * recency_decay) for all SUPPORTS
            - sum(w_tier * nli_confidence * recency_decay) for all REFUTES
    
    NEUTRAL items contribute 0.0.
    Returns a single float value.
    """
    if not evidence_items:
        return 0.0

    score = 0.0
    for item in evidence_items:
        label = (item.nli_label or "").upper().strip()
        if label not in ("SUPPORTS", "REFUTES"):
            continue

        tier = item.domain_tier if item.domain_tier in TIER_WEIGHTS else (1 if item.curated else 3)
        tier_weight = TIER_WEIGHTS.get(tier, 0.25)
        conf = float(item.nli_confidence) if item.nli_confidence is not None else 0.5
        decay = calculate_recency_decay(item.publish_date, reference_date)

        weighted_val = tier_weight * conf * decay

        if label == "SUPPORTS":
            score += weighted_val
        elif label == "REFUTES":
            score -= weighted_val

    return round(score, 4)


# ---------------------------------------------------------------------------
# Part 2 Verdicts and Aggregation
# ---------------------------------------------------------------------------
def calibrate_confidence(score: float, evidence_count: int, winning_label: str) -> float:
    """
    Calibrates confidence between 0.0 and 1.0 using score magnitude and evidence density.
    """
    if evidence_count == 0 or winning_label == "UNVERIFIED":
        return 0.0

    abs_score = abs(score)
    # Exponential mapping calibrated to score magnitude
    confidence = 1.0 - math.exp(-2.0 * abs_score)
    if abs_score >= TRUE_THRESHOLD:
        confidence = max(confidence, 0.75)
    return round(min(0.99, max(0.10, confidence)), 4)


def determine_sub_claim_verdict(
    sub_claim_id: str,
    sub_claim_text: str,
    evidence_items: List[EvidenceItem],
    reference_date: Optional[datetime] = None,
) -> SubClaimVerdict:
    """
    Evaluates evidence for a single sub-claim using explicit threshold constants.
    """
    score = calculate_sub_claim_score(evidence_items, reference_date=reference_date)

    supp_items = [e for e in evidence_items if (e.nli_label or "").upper() == "SUPPORTS"]
    ref_items = [e for e in evidence_items if (e.nli_label or "").upper() == "REFUTES"]
    neu_items = [e for e in evidence_items if (e.nli_label or "").upper() == "NEUTRAL"]
    active_evidence_count = len(supp_items) + len(ref_items)

    # 1. Total lack of active evidence -> Abstention
    if active_evidence_count == 0:
        verdict = "UNVERIFIED"
    # 2. Score decisively refutes the claim
    elif score <= FALSE_THRESHOLD:
        verdict = "FALSE"
    # 3. Score decisively supports the claim
    elif score >= TRUE_THRESHOLD:
        verdict = "TRUE"
    # 4. Intermediate zone (between FALSE_THRESHOLD and TRUE_THRESHOLD)
    else:
        # Score magnitude is negligible (< ABSTENTION_SCORE_THRESHOLD)
        if abs(score) < ABSTENTION_SCORE_THRESHOLD:
            # If both sides presented evidence, it's genuine controversy / mixed
            if supp_items and ref_items:
                verdict = "PARTIALLY TRUE"
            else:
                # Thin evidence on a single side with negligible score -> Abstain
                verdict = "UNVERIFIED"
        # Score is negative and refuting evidence outweighs or equals supporting
        elif score < 0 and len(ref_items) >= len(supp_items):
            verdict = "FALSE"
        # Score is positive and supporting evidence outweighs refuting
        elif score > 0 and len(supp_items) >= len(ref_items):
            verdict = "TRUE" if len(ref_items) == 0 else "PARTIALLY TRUE"
        else:
            verdict = "PARTIALLY TRUE" if (supp_items and ref_items) else "UNVERIFIED"

    confidence = calibrate_confidence(score, active_evidence_count, verdict)

    # Sort key evidence: supporting or refuting items with highest confidence
    sorted_ev = sorted(
        evidence_items,
        key=lambda x: (x.nli_confidence or 0.0) if (x.nli_label in ("SUPPORTS", "REFUTES")) else 0.0,
        reverse=True,
    )

    return SubClaimVerdict(
        sub_claim_id=sub_claim_id,
        sub_claim=sub_claim_text,
        score=score,
        verdict=verdict,
        confidence=confidence,
        evidence_count=len(evidence_items),
        supporting_count=len(supp_items),
        refuting_count=len(ref_items),
        neutral_count=len(neu_items),
        key_evidence=sorted_ev[:3],
    )


def aggregate_verdicts(
    raw_claim: str,
    sub_claim_verdicts: List[SubClaimVerdict],
) -> Tuple[str, float, float, bool]:
    """
    Deterministic aggregation rules across sub-claims:
      1. Any core sub-claim FALSE with high confidence -> Overall FALSE
      2. All sub-claims UNVERIFIED -> Overall UNVERIFIED (Abstention)
      3. All sub-claims TRUE -> Overall TRUE
      4. Mixed sub-claims -> Overall PARTIALLY TRUE
    
    Returns:
      (overall_verdict, overall_confidence, overall_score, is_abstained)
    """
    if not sub_claim_verdicts:
        return ("UNVERIFIED", 0.0, 0.0, True)

    total_score = sum(sc.score for sc in sub_claim_verdicts)
    avg_score = total_score / len(sub_claim_verdicts)

    false_verdicts = [sc for sc in sub_claim_verdicts if sc.verdict == "FALSE"]
    true_verdicts = [sc for sc in sub_claim_verdicts if sc.verdict == "TRUE"]
    unverified_verdicts = [sc for sc in sub_claim_verdicts if sc.verdict == "UNVERIFIED"]
    partial_verdicts = [sc for sc in sub_claim_verdicts if sc.verdict == "PARTIALLY TRUE"]

    # Rule 1: High-confidence False sub-claim taints composite claim
    high_conf_false = [f for f in false_verdicts if f.confidence >= HIGH_CONFIDENCE_THRESHOLD]
    if high_conf_false or len(false_verdicts) > len(true_verdicts):
        conf = max((f.confidence for f in false_verdicts), default=0.75)
        return ("FALSE", conf, round(avg_score, 4), False)

    # Rule 1b: If any sub-claim is False and overall average score is negative
    if false_verdicts and avg_score <= -0.15:
        conf = max((f.confidence for f in false_verdicts), default=0.70)
        return ("FALSE", conf, round(avg_score, 4), False)

    # Rule 2: Complete absence of verifiable evidence -> Abstention
    if len(unverified_verdicts) == len(sub_claim_verdicts):
        return ("UNVERIFIED", 0.0, 0.0, True)

    # Rule 3: All sub-claims True
    if len(true_verdicts) == len(sub_claim_verdicts):
        avg_conf = sum(t.confidence for t in true_verdicts) / len(true_verdicts)
        return ("TRUE", round(avg_conf, 4), round(avg_score, 4), False)

    # Rule 4: Mixed results (some TRUE, some FALSE, or PARTIALLY TRUE)
    if (true_verdicts and false_verdicts) or partial_verdicts:
        conf = 0.70
        return ("PARTIALLY TRUE", conf, round(avg_score, 4), False)

    # Rule 5: Some True with remaining Unverified
    if true_verdicts and not false_verdicts:
        avg_conf = sum(t.confidence for t in true_verdicts) / len(true_verdicts) * 0.8
        return ("PARTIALLY TRUE", round(avg_conf, 4), round(avg_score, 4), False)

    return ("UNVERIFIED", 0.0, 0.0, True)


# ---------------------------------------------------------------------------
# Part 3 The LLM Explanation (Narrator Only — Never Decides)
# ---------------------------------------------------------------------------
JUDGE_SYSTEM_PROMPT = """You are the Veritas Fact-Checking Auditor and Explainer.
A deterministic mathematical engine has already computed the final audit verdict:
OVERALL VERDICT: {overall_verdict} (Confidence: {overall_confidence:.1%})

YOUR MANDATE:
Write a clear, objective 3-5 sentence explanation justifying this exact verdict by citing the key evidence quotes and referencing their sources and URLs.

STRICT CONSTRAINTS:
1. THE JUDGE NARRATES, IT NEVER DECIDES. You must NEVER change or question the provided verdict.
2. If the verdict is UNVERIFIED, explicitly state that insufficient verified evidence exists in the curated and web corpora to establish or refute the claim with adequate confidence, demonstrating responsible epistemic abstention.
3. ONLY reference quotes, entities, and sources explicitly supplied below. Do not hallucinate external facts or invent quotes.
4. Keep the explanation professional, concise, and defensible for journalism and audits.
"""


def _generate_fallback_explanation(
    raw_claim: str,
    overall_verdict: str,
    overall_confidence: float,
    sub_claim_verdicts: List[SubClaimVerdict],
    is_abstained: bool,
) -> str:
    """Deterministic fallback explanation generator when LLM is unavailable or offline."""
    if is_abstained or overall_verdict == "UNVERIFIED":
        return (
            f"Veritas has abstained from rendering a definitive verdict on the claim \"{raw_claim}\" (verdict: UNVERIFIED). "
            f"Neither the curated fact-check vector store nor live web search returned sufficient high-confidence evidence "
            f"to establish or refute this assertion above the required credibility threshold. Epistemic abstention prevents "
            f"false confidence when source verification is thin."
        )

    sentences = [
        f"The composite claim \"{raw_claim}\" has been evaluated as {overall_verdict} "
        f"with a calibrated confidence of {overall_confidence:.1%}."
    ]

    for sc in sub_claim_verdicts:
        top_ev = sc.key_evidence[0] if sc.key_evidence else None
        if top_ev:
            source_info = top_ev.domain or top_ev.source_url
            sentences.append(
                f"Sub-claim \"{sc.sub_claim}\" was determined {sc.verdict} based on evidence from {source_info} "
                f"which stated: \"{top_ev.quote[:140]}...\"."
            )
        else:
            sentences.append(f"Sub-claim \"{sc.sub_claim}\" was evaluated as {sc.verdict}.")

    return " ".join(sentences[:4])


async def explain_verdict_with_llm(
    raw_claim: str,
    overall_verdict: str,
    overall_confidence: float,
    sub_claim_verdicts: List[SubClaimVerdict],
    is_abstained: bool,
) -> str:
    """
    Calls OpenAI to generate 3-5 narrative sentences citing evidence quotes.
    The LLM receives the already finalized verdict and acts purely as an auditor narrator.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        logger.info("OPENAI_API_KEY not configured; using deterministic explanation generator.")
        return _generate_fallback_explanation(
            raw_claim, overall_verdict, overall_confidence, sub_claim_verdicts, is_abstained
        )

    # Format sub-claims and evidence summaries
    sub_claim_lines = []
    for sc in sub_claim_verdicts:
        sub_claim_lines.append(
            f"- [{sc.sub_claim_id}] \"{sc.sub_claim}\" -> Verdict: {sc.verdict} (Score: {sc.score:+.2f}, Conf: {sc.confidence:.1%})"
        )
    sub_claim_summary = "\n".join(sub_claim_lines)

    evidence_lines = []
    for sc in sub_claim_verdicts:
        for ev in sc.key_evidence:
            evidence_lines.append(
                f"- For '{sc.sub_claim}': Quote: \"{ev.quote}\" | Source: {ev.domain or ev.source_url} | Label: {ev.nli_label}"
            )
    evidence_summary = "\n".join(evidence_lines) if evidence_lines else "No specific quotes available."

    system_content = JUDGE_SYSTEM_PROMPT.format(
        overall_verdict=overall_verdict,
        overall_confidence=overall_confidence,
    )
    user_content = (
        f"Claim: \"{raw_claim}\"\n\n"
        f"Sub-Claims Breakdown:\n{sub_claim_summary}\n\n"
        f"Retrieved Quotes:\n{evidence_summary}\n\n"
        f"Write the 3-5 sentence audit explanation."
    )

    try:
        client = AsyncOpenAI(api_key=api_key.strip())
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=350,
        )
        explanation = resp.choices[0].message.content.strip()
        return explanation
    except Exception as exc:
        logger.warning(f"LLM explanation call encountered error ({exc}); using fallback generator.")
        return _generate_fallback_explanation(
            raw_claim, overall_verdict, overall_confidence, sub_claim_verdicts, is_abstained
        )


# ---------------------------------------------------------------------------
# Main Orchestrator Function: judge_evaluate_claim
# ---------------------------------------------------------------------------
@observe(name="judge_evaluate_claim")
async def judge_evaluate_claim(
    raw_claim: str,
    sub_claims: List[SubClaim],
    evidence_items: List[EvidenceItem],
    generate_explanation: bool = True,
    reference_date: Optional[datetime] = None,
) -> JudgeVerdictResponse:
    """
    Main entry point for Judge Agent.
    
    Step 1: Groups evidence by sub_claim_id.
    Step 2: Deterministically computes mathematical score and verdict per sub-claim.
    Step 3: Aggregates sub-claim verdicts into final verdict & confidence (with abstention).
    Step 4: LLM narrates 3-5 sentence explanation citing evidence (narrator only, never decides).
    """
    # Group evidence items by sub_claim_id
    evidence_by_id: Dict[str, List[EvidenceItem]] = {}
    for ev in evidence_items:
        evidence_by_id.setdefault(ev.sub_claim_id, []).append(ev)

    # Part 1 & 2: Deterministic per-sub-claim evaluation
    sub_claim_verdicts: List[SubClaimVerdict] = []
    for sc in sub_claims:
        sc_ev = evidence_by_id.get(sc.id, [])
        sc_verdict = determine_sub_claim_verdict(
            sub_claim_id=sc.id,
            sub_claim_text=sc.text,
            evidence_items=sc_ev,
            reference_date=reference_date,
        )
        sub_claim_verdicts.append(sc_verdict)

    # Part 2: Deterministic overall aggregation
    overall_verdict, overall_conf, overall_score, is_abstained = aggregate_verdicts(
        raw_claim=raw_claim,
        sub_claim_verdicts=sub_claim_verdicts,
    )

    # Extract unique key citation URLs
    citations: List[str] = []
    for sc in sub_claim_verdicts:
        for ev in sc.key_evidence:
            if ev.source_url and ev.source_url not in citations:
                citations.append(ev.source_url)

    # Part 3: LLM Explanation narrative
    if generate_explanation:
        explanation = await explain_verdict_with_llm(
            raw_claim=raw_claim,
            overall_verdict=overall_verdict,
            overall_confidence=overall_conf,
            sub_claim_verdicts=sub_claim_verdicts,
            is_abstained=is_abstained,
        )
    else:
        explanation = _generate_fallback_explanation(
            raw_claim, overall_verdict, overall_conf, sub_claim_verdicts, is_abstained
        )

    logger.info(
        "Judge evaluation complete for '%s' | Verdict: %s (Confidence: %.1f%%, Abstained: %s)",
        raw_claim[:60],
        overall_verdict,
        overall_conf * 100,
        is_abstained,
    )

    return JudgeVerdictResponse(
        raw_claim=raw_claim,
        overall_verdict=overall_verdict,
        overall_confidence=overall_conf,
        overall_score=overall_score,
        is_abstained=is_abstained,
        sub_claim_verdicts=sub_claim_verdicts,
        explanation=explanation,
        key_citations=citations,
    )


__all__ = [
    "TIER_WEIGHTS",
    "TRUE_THRESHOLD",
    "FALSE_THRESHOLD",
    "ABSTENTION_SCORE_THRESHOLD",
    "MIN_EVIDENCE_COUNT",
    "HIGH_CONFIDENCE_THRESHOLD",
    "calculate_recency_decay",
    "calculate_sub_claim_score",
    "determine_sub_claim_verdict",
    "aggregate_verdicts",
    "judge_evaluate_claim",
    "explain_verdict_with_llm",
]
