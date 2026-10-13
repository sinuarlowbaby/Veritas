import pytest
from app.services.semantic_cache import SemanticCache, cosine_similarity
from app.database import SessionLocal
from app.models.db_models import SemanticCacheORM


@pytest.fixture(autouse=True)
def clean_cache():
    session = SessionLocal()
    session.query(SemanticCacheORM).delete()
    session.commit()
    session.close()
    yield
    session = SessionLocal()
    session.query(SemanticCacheORM).delete()
    session.commit()
    session.close()


def test_cosine_similarity_calculation():
    vec_1 = [1.0, 0.0, 0.0]
    vec_2 = [1.0, 0.0, 0.0]
    assert cosine_similarity(vec_1, vec_2) == pytest.approx(1.0, rel=1e-4)

    vec_3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(vec_1, vec_3) == pytest.approx(0.0, rel=1e-4)

    vec_4 = [1.0, 1.0, 0.0]
    assert cosine_similarity(vec_1, vec_4) == pytest.approx(0.7071, rel=1e-3)


def test_semantic_cache_store_and_match():
    cache = SemanticCache(similarity_threshold=0.85)

    base_vec = [0.1] * 1536
    result_data = {
        "verdict": "FALSE",
        "confidence": 0.99,
        "explanation": "Doctors confirm papaya seeds do not cure dengue.",
    }

    # Store entry
    cache.store(
        claim_text="Papaya leaves cure dengue virus completely",
        result_dict=result_data,
        claim_embedding=base_vec,
        verdict="FALSE",
        confidence=0.99,
    )

    # 1. Exact or near-identical vector match (sim = 1.0)
    match_hit = cache.find_match(
        claim_text="Can consuming papaya leaf juice eliminate dengue?",
        claim_embedding=base_vec,
        threshold=0.85,
    )
    assert match_hit is not None
    cached_res, sim, matched_claim = match_hit
    assert cached_res["verdict"] == "FALSE"
    assert sim >= 0.99
    assert "papaya" in matched_claim.lower()

    # 2. Unrelated vector (orthogonal vector)
    unrelated_vec = [-0.1 if i % 2 == 0 else 0.1 for i in range(1536)]
    match_miss = cache.find_match(
        claim_text="Moon landing was staged in Hollywood studio",
        claim_embedding=unrelated_vec,
        threshold=0.85,
    )
    assert match_miss is None
