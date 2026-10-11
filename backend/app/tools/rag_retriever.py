import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables (.env from backend or root)
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
else:
    load_dotenv()

from app.models.schemas import CuratedFactChunk, SearchResult
from app.services.vector_store import VectorStore

logger = logging.getLogger("veritas.tools.rag_retriever")

# Observability setup (Langfuse)
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY")
    and os.getenv("LANGFUSE_SECRET_KEY")
    and os.getenv("LANGFUSE_PUBLIC_KEY").strip()
    and os.getenv("LANGFUSE_SECRET_KEY").strip()
)

if LANGFUSE_ENABLED:
    from langfuse import observe
    logger.info("Langfuse tracking enabled for RAG Retriever.")
else:
    def observe(*args, **kwargs):
        """Pass-through decorator when Langfuse is not enabled."""
        def decorator(fn):
            return fn
        return decorator

    logger.info("Langfuse credentials not set; running RAG Retriever with standard logging.")


# ---------------------------------------------------------------------------
# Embedding Generator (OpenAI text-embedding-3-small)
# ---------------------------------------------------------------------------
async def embed_text(text: str) -> List[float]:
    """
    Generate a 1536-dimensional dense vector embedding using OpenAI text-embedding-3-small.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("OPENAI_API_KEY environment variable is not configured.")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key.strip())
    resp = await client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return resp.data[0].embedding


# ---------------------------------------------------------------------------
# Canonical Seed Corpus Data (IFCN Signatories & Ground Truth Fact-Checks)
# ---------------------------------------------------------------------------
CANONICAL_SEED_FACTS = [
    {
        "title": "Fact Check: Papaya leaf extract and seeds do not cure dengue fever, doctors clarify",
        "source_url": "https://www.boomlive.in/fact-check/health/papaya-leaf-juice-seeds-cannot-cure-dengue-19842",
        "source_name": "BoomLive",
        "verdict": "FALSE",
        "publish_date": "2023-09-18",
        "chunk_text": (
            "Viral social media posts claim that consuming papaya leaves, papaya seed powder, or fresh papaya juice "
            "completely cures dengue infection within 24 to 48 hours and eliminates the need for hospitalization. "
            "Health experts and the World Health Organization (WHO) have clarified that there is no antiviral cure for dengue "
            "in modern or traditional medicine. While some pilot trials observed mild increases in platelet counts, papaya seeds "
            "or leaves do not kill the dengue virus nor prevent severe dengue hemorrhagic fever and plasma leakage. "
            "Medical supervision, proper intravenous hydration, and close platelet monitoring remain the only recognized clinical "
            "protocols. Relying solely on papaya seeds can delay critical hospital care and result in fatal dengue shock syndrome."
        ),
    },
    {
        "title": "Fact Check: UNESCO did not declare India's national anthem 'Jana Gana Mana' as the best in the world",
        "source_url": "https://www.altnews.in/unesco-best-national-anthem-hoax-resurfaces-social-media/",
        "source_name": "Alt News",
        "verdict": "FALSE",
        "publish_date": "2022-08-14",
        "chunk_text": (
            "A perennial viral message shared extensively across WhatsApp, Facebook, and Twitter asserts that the United Nations "
            "Educational, Scientific and Cultural Organization (UNESCO) has declared India's national anthem 'Jana Gana Mana' as the "
            "'Best National Anthem in the World'. This assertion is completely baseless. UNESCO has categorically confirmed on "
            "multiple occasions that it never assesses, judges, or ranks national anthems of sovereign countries. Sue Williams, "
            "Chief of Media Relations at UNESCO, confirmed via official correspondence that no such declaration or competition has "
            "ever taken place. The message is a long-running internet hoax that originated in 2008 and frequently resurfaces during national holidays."
        ),
    },
    {
        "title": "Fact Check: The 1969 Apollo 11 moon landing was not staged on a Hollywood film set",
        "source_url": "https://www.snopes.com/fact-check/apollo-moon-landing-conspiracy-hollywood/",
        "source_name": "Snopes",
        "verdict": "FALSE",
        "publish_date": "2021-07-20",
        "chunk_text": (
            "Conspiracy theorists continue to promote claims that NASA staged the 1969 Apollo 11 lunar landing in a Hollywood "
            "television studio directed by Stanley Kubrick, alleging the United States faked the event to win the space race against "
            "the Soviet Union. Extensive, independently verifiable evidence refutes this claim. Retroreflectors placed by Apollo "
            "astronauts on the lunar surface are still pinged with lasers by independent observatories across the globe to measure the "
            "Earth-Moon distance. Furthermore, 382 kilograms of lunar soil and rock samples analyzed by scientists globally exhibit "
            "impact cratering and solar wind radiation signatures impossible to fabricate on Earth. The Soviet Union, having tracked "
            "the Apollo telemetry in real time during the Cold War, never disputed the landing."
        ),
    },
    {
        "title": "Fact Check: WHO did not confirm that green tea cures COVID-19 in 48 hours",
        "source_url": "https://www.boomlive.in/fact-check/who-green-tea-covid-19-cure-claim-fake-news-14251",
        "source_name": "BoomLive",
        "verdict": "FALSE",
        "publish_date": "2021-05-10",
        "chunk_text": (
            "A viral message attributed to the World Health Organization (WHO) claims that drinking hot green tea cures COVID-19 "
            "within 48 hours and has saved over 50,000 lives across India. The post urges patients to substitute hospital treatment "
            "with three cups of green tea daily. The WHO Regional Office has clarified that this message is entirely fabricated. "
            "No such advisory or confirmation was issued. While green tea contains polyphenols and antioxidants, there is zero "
            "scientific or clinical evidence indicating it can neutralize the SARS-CoV-2 coronavirus or cure acute respiratory distress "
            "in infected patients. Health authorities caution that circulating unverified home remedies undermines clinical care and patient survival."
        ),
    },
    {
        "title": "Fact Check: Mysterious bird deaths in Delhi are not caused by 5G mobile tower radiation",
        "source_url": "https://www.altnews.in/viral-claim-linking-5g-trials-to-bird-deaths-in-delhi-is-baseless/",
        "source_name": "Alt News",
        "verdict": "FALSE",
        "publish_date": "2021-06-02",
        "chunk_text": (
            "Social media posts featuring photographs of dead birds in Delhi claim that test radiation from 5G telecom towers caused "
            "sudden avian mortality, prompting the Indian government to issue an immediate ban on 5G installations. The Department of "
            "Telecommunications (DoT) and the Press Information Bureau (PIB) fact-checking unit confirmed that no ban on 5G has been "
            "ordered and the correlation is fabricated. Veterinary investigations conducted by the National Institute of High Security "
            "Animal Diseases (NIHSAD) revealed that the bird fatalities were caused by the H5N8 avian influenza virus, not electromagnetic "
            "radiation. RF radiation from telecommunication towers operates well within non-ionizing safety thresholds approved by international guidelines."
        ),
    },
    {
        "title": "Fact Check: Ministry of Finance has not exempted citizens over 60 from all income tax",
        "source_url": "https://factcheck.pib.gov.in/policy/income-tax-senior-citizens-exemption-claim-false",
        "source_name": "PIB Fact Check",
        "verdict": "FALSE",
        "publish_date": "2024-03-25",
        "chunk_text": (
            "A widely forwarded financial claim alleges that the Ministry of Finance has eliminated all income tax for Indian citizens "
            "over 60 years old starting April 1, resulting in an estimated Rs 40,000 crore revenue loss. The Press Information Bureau "
            "Fact Check unit verified with the Ministry of Finance that this claim is false. The government has made no announcement "
            "granting a blanket income tax waiver for all senior citizens. Standard tax slabs, rebate provisions under Section 87A, "
            "and deductions under Section 80TTB for interest income continue to apply under both the Old and New Tax Regimes as stipulated "
            "in the Finance Act. No sudden policy abolishing tax liabilities for retirees has been enacted."
        ),
    },
    {
        "title": "Fact Check: ISRO's Chandrayaan-3 successfully achieved soft landing near lunar south pole",
        "source_url": "https://www.reuters.com/fact-check/isro-chandrayaan-3-moon-landing-verified-2023-08-24/",
        "source_name": "Reuters Fact Check",
        "verdict": "TRUE",
        "publish_date": "2023-08-24",
        "chunk_text": (
            "Following the historic landing of India's Chandrayaan-3 spacecraft on August 23, 2023, viral posts questioned whether the "
            "Vikram lander actually touched down or if ISRO broadcast computer-generated simulations. International space agencies "
            "including NASA and ESA independently confirmed live tracking and telemetry from the lander on the lunar south pole. "
            "NASA's Lunar Reconnaissance Orbiter (LRO) captured high-resolution orbital imagery of the Vikram lander resting on the Moon's "
            "surface with visible rocket plume blast halo marks. Physical scientific payloads including ChaSTE and RAMBHA transmitted verified "
            "surface temperature and plasma density measurements back to Earth, confirming genuine soft landing."
        ),
    },
]


async def ensure_curated_corpus_seeded(vector_store: Optional[VectorStore] = None) -> int:
    """
    Ensure the vector store has the canonical curated fact-check chunks seeded with embeddings.
    If empty, embeds and inserts the seed corpus into the vector store.
    """
    store = vector_store or VectorStore()
    if store.count() > 0:
        return store.count()

    logger.info("Vector store is empty. Seeding canonical curated fact-check chunks...")
    chunks_to_insert: List[CuratedFactChunk] = []

    for idx, item in enumerate(CANONICAL_SEED_FACTS):
        # Generate dense vector embedding for the chunk text
        embedding = await embed_text(item["chunk_text"])
        chunks_to_insert.append(
            CuratedFactChunk(
                title=item["title"],
                source_url=item["source_url"],
                source_name=item["source_name"],
                verdict=item["verdict"],
                publish_date=item["publish_date"],
                chunk_index=0,
                chunk_text=item["chunk_text"],
                embedding=embedding,
            )
        )

    inserted_count = store.insert_chunks(chunks_to_insert)
    logger.info(f"Successfully seeded {inserted_count} curated fact chunks.")
    return inserted_count


# ---------------------------------------------------------------------------
# Core Async RAG Retriever Function (Interchangeable with search_web)
# ---------------------------------------------------------------------------
@observe(name="retrieve_curated_evidence")
async def retrieve_curated_evidence(
    query: Optional[str] = None,
    sub_claim: Optional[str] = None,
    top_k: int = 5,
    min_similarity: float = 0.0,
    vector_store: Optional[VectorStore] = None,
) -> List[SearchResult]:
    """
    Retrieve curated fact-check evidence for a sub-claim.
    
    1. Embeds the input query string using text-embedding-3-small.
    2. Executes cosine similarity query against pgvector (or local store fallback).
    3. Returns top-k matching chunks formatted as SearchResult items with
       full metadata: title, url, snippet, content, source, verdict, publish_date, and similarity.

    Returns the same evidence-like shape as search_web so both tools are interchangeable.

    Args:
        query: Search query or claim string.
        sub_claim: Alias for query.
        top_k: Maximum number of chunks to return (default: 5).
        min_similarity: Minimum cosine similarity threshold (default: 0.0).
        vector_store: Optional injected VectorStore instance.

    Returns:
        List[SearchResult] with verdict and similarity metadata populated.
    """
    resolved_query = (query or sub_claim or "").strip()
    if not resolved_query:
        return []

    store = vector_store or VectorStore()

    # Ensure curated facts are seeded
    if store.count() == 0:
        await ensure_curated_corpus_seeded(store)

    # Step 1: Embed the sub-claim
    query_vector = await embed_text(resolved_query)

    # Step 2: Query the vector store
    matched_chunks = store.search_similar(
        query_embedding=query_vector,
        top_k=top_k,
        min_similarity=min_similarity,
    )

    # Step 3: Transform into uniform SearchResult evidence shape
    results: List[SearchResult] = []
    for chunk in matched_chunks:
        # Generate snippet summary from chunk text
        snippet_text = (
            chunk.chunk_text[:240] + ("..." if len(chunk.chunk_text) > 240 else "")
        )
        results.append(
            SearchResult(
                title=chunk.title,
                url=chunk.source_url,
                snippet=snippet_text,
                content=chunk.chunk_text,
                source=f"curated_rag:{chunk.source_name}",
                verdict=chunk.verdict,
                publish_date=chunk.publish_date,
                similarity=chunk.similarity,
            )
        )

    logger.info(
        "RAG retrieval completed for query '%s' | returned %d chunks (top similarity: %s)",
        resolved_query[:60],
        len(results),
        f"{results[0].similarity:.4f}" if results and results[0].similarity else "N/A",
    )

    return results


# Aliases for flexible integration across agents
rag_retriever = retrieve_curated_evidence
query_vector_store = retrieve_curated_evidence

__all__ = [
    "retrieve_curated_evidence",
    "rag_retriever",
    "query_vector_store",
    "embed_text",
    "ensure_curated_corpus_seeded",
    "CANONICAL_SEED_FACTS",
]
