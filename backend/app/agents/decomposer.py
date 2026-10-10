import logging
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables (.env from backend or root)
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

from app.models.schemas import DecomposeResponse, SubClaim

logger = logging.getLogger("veritas.decomposer")

# Check if Langfuse credentials are provided
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    from langfuse.openai import AsyncOpenAI

    logger.info("Langfuse tracking enabled for Claim Decomposer.")
else:
    from openai import AsyncOpenAI

    def observe(*args, **kwargs):
        """Pass-through decorator when Langfuse is not enabled."""
        def decorator(fn):
            return fn
        return decorator

    logger.info("Langfuse credentials not set; running with standard AsyncOpenAI client.")


DECOMPOSER_SYSTEM_PROMPT = """You are an expert fact-checking Claim Decomposer in an adversarial verification system.
Your mission is to take a raw, often complex, misleading, or composite headline/claim, and decompose it into distinct, atomic, independently checkable sub-claims.

Rules for decomposition:
1. ATOMICITY: Each sub-claim must contain exactly ONE testable assertion of fact. Split compound sentences joined by conjunctions ('and', 'but', 'because', 'while', 'as well as').
2. INDEPENDENCE: Each sub-claim must make sense on its own. Resolve all pronouns ('he', 'she', 'they', 'it', 'this') and relative references to the explicit named entity.
3. ATTRIBUTION vs FACT: When a statement claims an organization/person made an announcement, report, or finding (e.g., 'WHO confirms X', 'Finance Ministry announces Y'), split the attribution ('Entity stated X') from the underlying factual occurrence ('X occurred') if both are asserted.
4. NUMERICAL & TEMPORAL METRICS: Isolate specific dates, amounts of money, percentages, and casualty/people numbers into separate verifiable statements.
5. OBJECTIVITY: Formulate each sub-claim neutrally without sensationalism, sarcasm, or editorializing.
6. FIDELITY: Strictly extract assertions present or directly implied in the input. Never invent claims that were not asserted.

Classify each sub-claim with one of these types:
- 'factual_event': An action, event, or occurrence.
- 'statistical_quantity': A numerical claim, currency amount, percentage, or date.
- 'attribution': A claim that a specific entity/person stated, claimed, or announced something.
- 'causal_effect': A claim that X caused, led to, or cured Y.
- 'general': Any other verifiable assertion.
"""


class LLMSubClaim(BaseModel):
    text: str = Field(
        ...,
        description="Atomic, self-contained factual assertion with pronouns resolved.",
    )
    type: str = Field(
        ...,
        description="Assertion type: 'factual_event', 'statistical_quantity', 'attribution', 'causal_effect', or 'general'.",
    )


class LLMDecompositionOutput(BaseModel):
    sub_claims: List[LLMSubClaim] = Field(
        ...,
        description="List of atomic sub-claims extracted from the claim.",
    )


@observe(name="decompose_claim")
async def decompose_claim(
    raw_input: str,
    model: str = "gpt-4o-mini",
) -> DecomposeResponse:
    """
    Decomposes a raw composite claim or headline into atomic, independently checkable sub-claims
    using a single structured LLM call. Automatically traced with Langfuse if configured.
    """
    client = AsyncOpenAI()

    logger.info(f"Decomposing claim: {raw_input[:60]}... using {model}")

    completion = await client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": DECOMPOSER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Decompose the following input into atomic sub-claims:\n\n\"{raw_input.strip()}\"",
            },
        ],
        response_format=LLMDecompositionOutput,
        temperature=0.0,
    )

    parsed = completion.choices[0].message.parsed
    raw_sub_claims = parsed.sub_claims if parsed else []

    sub_claims = [
        SubClaim(
            id=f"subclaim_{idx + 1}",
            text=item.text.strip(),
            type=item.type.strip(),
        )
        for idx, item in enumerate(raw_sub_claims)
    ]

    logger.info(f"Successfully decomposed into {len(sub_claims)} atomic sub-claims.")

    return DecomposeResponse(
        raw_input=raw_input,
        sub_claims=sub_claims,
        total_sub_claims=len(sub_claims),
    )
