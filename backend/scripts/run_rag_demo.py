import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.tools.rag_retriever import retrieve_curated_evidence
from app.tools.web_search import search_web


async def main():
    print("=" * 80)
    print("STEP B: TESTING RAG RETRIEVER ON REAL SUB-CLAIMS & OUT-OF-CORPUS CLAIMS")
    print("=" * 80)

    # 1. Dengue cures query
    dengue_query = "Can papaya seeds or leaf extract cure dengue fever?"
    print(f"\n[Test 1] Dengue Relevance Check")
    print(f"Query: \"{dengue_query}\"")
    dengue_results = await retrieve_curated_evidence(query=dengue_query, top_k=5)
    for i, r in enumerate(dengue_results):
        print(f"  Rank {i+1} [Similarity: {r.similarity:.4f}] | Verdict: {r.verdict} | Source: {r.source}")
        print(f"         Title: {r.title}")
        print(f"         Snippet: {r.snippet[:130]}...\n")

    # 2. Decomposer Sub-Claims
    sub_claims = [
        "WHO officially confirmed green tea cures COVID-19 in 48 hours",
        "5G mobile tower radiation caused mysterious bird deaths in Delhi",
        "Finance Ministry eliminated all income tax for citizens over 60 years old",
    ]
    print("-" * 80)
    print("[Test 2] Decomposer Sub-Claims Relevance Checks")
    for sc in sub_claims:
        res = await retrieve_curated_evidence(query=sc, top_k=2)
        top = res[0]
        print(f"\nSub-Claim: \"{sc}\"")
        print(f"  Top Match [Similarity: {top.similarity:.4f}] | Verdict: {top.verdict} | Source: {top.source}")
        print(f"  Title: {top.title}")

    # 3. Out-of-Corpus Queries (Cricket & Cinema)
    out_of_corpus = [
        "Virat Kohli scored his 50th century in the ODI World Cup semi-final at Wankhede Stadium",
        "Shah Rukh Khan's movie Jawan broke box office records across Mumbai theaters",
    ]
    print("\n" + "-" * 80)
    print("[Test 3] Out-of-Corpus Discrimination Checks (Cricket & Cinema)")
    for ooc in out_of_corpus:
        res = await retrieve_curated_evidence(query=ooc, top_k=3)
        top = res[0]
        print(f"\nQuery: \"{ooc}\"")
        print(f"  Top Similarity Score: {top.similarity:.4f} (LOW SIGNAL -> Triggers Judge Abstention / Web Fallback)")
        print(f"  Top Match in Corpus: {top.title} [Verdict: {top.verdict}]")

    print("\n" + "=" * 80)
    print("STEP C: SIDE-BY-SIDE COMPARISON (RAG RETRIEVER VS LIVE WEB SEARCH)")
    print("=" * 80)

    comparison_claim = "WHO officially confirms green tea cures COVID-19 in 48 hours"
    print(f"\nSub-Claim Evaluated: \"{comparison_claim}\"\n")

    rag_evidence = await retrieve_curated_evidence(query=comparison_claim, top_k=2)
    web_evidence = await search_web(query=comparison_claim, max_results=2)

    print("-" * 80)
    print("1. CURATED RAG RETRIEVER RESULT (Structured Ground-Truth)")
    print("-" * 80)
    for i, r in enumerate(rag_evidence):
        print(f"Chunk {i+1}:")
        print(f"  Title:        {r.title}")
        print(f"  Source:       {r.source}")
        print(f"  URL:          {r.url}")
        print(f"  Verdict:      {r.verdict}  <-- PROFESSIONAL FACT-CHECK VERDICT")
        print(f"  Publish Date: {r.publish_date}")
        print(f"  Similarity:   {r.similarity:.4f}")
        print(f"  Snippet:      {r.snippet[:160]}...\n")

    print("-" * 80)
    print("2. LIVE WEB SEARCH RESULT (Unstructured Live Web)")
    print("-" * 80)
    for i, w in enumerate(web_evidence):
        print(f"Result {i+1}:")
        print(f"  Title:        {w.title}")
        print(f"  Source:       {w.source}")
        print(f"  URL:          {w.url}")
        print(f"  Verdict:      {w.verdict}  <-- NO VERDICT (RAW WEB CONTENT)")
        print(f"  Publish Date: {w.publish_date}")
        print(f"  Similarity:   {w.similarity}")
        print(f"  Snippet:      {w.snippet[:160]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
