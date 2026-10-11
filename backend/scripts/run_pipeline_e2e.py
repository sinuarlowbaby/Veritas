import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.graph import run_verification_pipeline
from app.services.nli_verifier import get_nli_verifier

TEST_CASES = [
    {
        "name": "Headline 1: Health Misinformation (Green Tea COVID Cure)",
        "headline": "WHO officially confirms green tea cures COVID-19 in 48 hours, saving 50,000 lives in India last month",
        "expected_verdict": "FALSE",
    },
    {
        "name": "Headline 2: Fiscal & Policy Rumor (Income Tax Elimination)",
        "headline": "Finance Ministry eliminates all income tax for citizens over 60 starting April 1, causing Rs 40,000 crore revenue loss",
        "expected_verdict": "FALSE",
    },
    {
        "name": "Headline 3: Viral Conspiracy (5G Radiation Bird Deaths)",
        "headline": "Government orders immediate ban on 5G mobile towers because radiation caused mysterious bird deaths in Delhi",
        "expected_verdict": "FALSE",
    },
    {
        "name": "Headline 4: Obscure Fictional Claim (Epistemic Abstention)",
        "headline": "Local resident Rameshwar Patel of village Bilaspur discovered a 17-pound iridescent glowing sapphire inside a wild papaya on October 8, 2026",
        "expected_verdict": "UNVERIFIED",
    },
]


async def main():
    print("=" * 85)
    print("      VERITAS END-TO-END MULTI-AGENT PIPELINE TERMINAL TEST")
    print("=" * 85)
    print("Pipeline Flow: Headline In -> Sub-Claims -> Adversarial Evidence ->")
    print("               Sanitizer -> NLI Labels -> Math Scoring -> Judge Verdict + Explanation Out")
    print("=" * 85)

    # Preload NLI Cross-Encoder once
    print("\n[Lifespan] Preloading NLI Cross-Encoder model...")
    t0 = time.perf_counter()
    verifier = get_nli_verifier()
    verifier.load_model()
    print(f"[Lifespan] Cross-Encoder loaded in {time.perf_counter() - t0:.2f}s.\n")

    for idx, case in enumerate(TEST_CASES, 1):
        name = case["name"]
        headline = case["headline"]
        expected = case["expected_verdict"]

        print("=" * 85)
        print(f"[{idx}/{len(TEST_CASES)}] CASE: {name}")
        print(f"HEADLINE: \"{headline}\"")
        print(f"EXPECTED SANITY VERDICT: {expected}")
        print("-" * 85)

        start_time = time.perf_counter()

        def on_stage_update(stage: str):
            print(f"  [Pipeline Status] --> {stage}")

        try:
            verdict_response = await run_verification_pipeline(
                raw_claim=headline,
                status_callback=on_stage_update,
                generate_explanation=True,
            )
            elapsed = time.perf_counter() - start_time

            print("\n" + "=" * 35 + " VERDICT AUDIT " + "=" * 35)
            print(f"OVERALL VERDICT    : {verdict_response.overall_verdict}")
            print(f"OVERALL CONFIDENCE : {verdict_response.overall_confidence:.2%}")
            print(f"OVERALL SCORE      : {verdict_response.overall_score:+.4f}")
            print(f"EPISTEMIC ABSTAINED: {verdict_response.is_abstained}")
            print(f"EXECUTION TIME     : {elapsed:.2f}s")

            print("\nATOMIC SUB-CLAIMS & SCORES:")
            for sc_v in verdict_response.sub_claim_verdicts:
                print(f"  - [{sc_v.sub_claim_id}] Verdict: {sc_v.verdict:<14} | Score: {sc_v.score:+.3f} | Conf: {sc_v.confidence:.2%}")
                print(f"    Sub-Claim: \"{sc_v.sub_claim}\"")
                print(f"    Evidence Stats: {sc_v.evidence_count} items (SUPPORTS: {sc_v.supporting_count}, REFUTES: {sc_v.refuting_count}, NEUTRAL: {sc_v.neutral_count})")
                if sc_v.key_evidence:
                    print("    Top Key Evidence:")
                    for ev in sc_v.key_evidence[:2]:
                        print(f"      * [{ev.nli_label} {ev.nli_confidence:.1%}] (Tier {ev.domain_tier} - {ev.domain}): \"{ev.quote[:100]}...\"")

            print("\nNARRATIVE EXPLANATION (LLM AUDIT NARRATOR):")
            print(f"  {verdict_response.explanation}")

            if verdict_response.key_citations:
                print("\nKEY CITATIONS:")
                for cit in verdict_response.key_citations:
                    print(f"  - {cit}")

            # Sanity assertion check
            matches_expected = verdict_response.overall_verdict == expected
            print("\nSANITY CHECK RESULT: " + ("PASS (Matches Expected)" if matches_expected else f"DIVERGENCE (Got {verdict_response.overall_verdict}, Expected {expected})"))
            print("=" * 85 + "\n")

        except Exception as exc:
            print(f"\n[ERROR] Pipeline run failed: {exc}")
            import traceback
            traceback.print_exc()

    print("=" * 85)
    print("ALL END-TO-END PIPELINE TESTS COMPLETED.")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(main())
