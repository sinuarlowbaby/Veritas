from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field



class SubClaim(BaseModel):
    id: str = Field(
        ...,
        description="Unique identifier for the sub-claim, e.g., 'subclaim_1', 'subclaim_2'.",
    )
    text: str = Field(
        ...,
        description="Atomic, self-contained factual assertion with pronouns and references resolved.",
    )
    type: str = Field(
        default="general",
        description="Category: 'factual_event', 'statistical_quantity', 'attribution', 'causal_effect', or 'general'.",
    )


class DecomposeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=3,
        description="Raw headline, article excerpt, or composite claim to decompose.",
    )


class DecomposeResponse(BaseModel):
    raw_input: str = Field(
        ...,
        description="The original user-submitted headline or claim text.",
    )
    sub_claims: List[SubClaim] = Field(
        default_factory=list,
        description="List of atomic, independently verifiable sub-claims.",
    )
    total_sub_claims: int = Field(
        ...,
        description="Total number of decomposed sub-claims.",
    )


class SearchResult(BaseModel):
    title: str = Field(
        ...,
        description="Headline or title of the search result.",
    )
    url: str = Field(
        ...,
        description="URL of the web page.",
    )
    snippet: str = Field(
        default="",
        description="Search snippet or summary text.",
    )
    content: str = Field(
        default="",
        description="Extracted page text or rendered content.",
    )
    source: str = Field(
        ...,
        description="Search provider or source (e.g., 'tinyfish', 'tavily', 'duckduckgo', 'curated_rag').",
    )
    verdict: Optional[str] = Field(
        default=None,
        description="Fact-checker verdict if available (e.g., 'FALSE', 'TRUE', 'MISLEADING').",
    )
    publish_date: Optional[str] = Field(
        default=None,
        description="Publication date of the source article (YYYY-MM-DD).",
    )
    similarity: Optional[float] = Field(
        default=None,
        description="Cosine similarity score for vector retrieval.",
    )


class SearchRequest(BaseModel):
    question: str = Field(
        default="",
        description="The question or claim to search on the live web.",
    )
    query: str = Field(
        default="",
        description="Alternative alias for question.",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of search results to retrieve.",
    )

    def resolved_query(self) -> str:
        val = (self.question or self.query or "").strip()
        if len(val) < 2:
            raise ValueError("Please provide a question or query with at least 2 characters.")
        return val


class SearchResponse(BaseModel):
    question: str = Field(
        ...,
        description="The question or query submitted.",
    )
    provider_used: str = Field(
        ...,
        description="Search provider that fulfilled the request ('tinyfish', 'tavily', or 'duckduckgo').",
    )
    total_results: int = Field(
        ...,
        description="Number of search results returned.",
    )
    results: List[SearchResult] = Field(
        default_factory=list,
        description="List of search results including clean extracted page text.",
    )


class BatchQuestionsRequest(BaseModel):
    questions: List[str] = Field(
        ...,
        min_length=1,
        description="List of questions or sub-claims to search.",
    )
    max_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum search results per question.",
    )


class BatchQuestionsResponse(BaseModel):
    total_questions: int = Field(
        ...,
        description="Total number of questions processed.",
    )
    responses: List[SearchResponse] = Field(
        default_factory=list,
        description="List of search results per question.",
    )


class CuratedFactChunk(BaseModel):
    id: Optional[Union[str, int]] = Field(
        default=None,
        description="Unique database identifier for the chunk.",
    )
    title: str = Field(
        ...,
        description="Title of the fact-check article.",
    )
    source_url: str = Field(
        ...,
        description="URL of the fact-check publication.",
    )
    source_name: str = Field(
        ...,
        description="Name of the fact-checking agency (e.g. 'Alt News', 'Boom', 'Snopes').",
    )
    verdict: str = Field(
        ...,
        description="Fact-checker's published verdict (e.g. 'FALSE', 'TRUE', 'PARTIALLY TRUE', 'SATIRE', 'MISLEADING').",
    )
    publish_date: str = Field(
        ...,
        description="Publication date of the fact-check (YYYY-MM-DD).",
    )
    chunk_index: int = Field(
        default=0,
        description="Zero-based index of this chunk within the original article.",
    )
    chunk_text: str = Field(
        ...,
        description="The verbatim ~300-500 word text of the chunk.",
    )
    similarity: Optional[float] = Field(
        default=None,
        description="Cosine similarity score against the search query.",
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding (1536-dim for text-embedding-3-small).",
    )


class CuratedFactSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=2,
        description="Claim or search query to look up against curated fact-checks.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of curated chunks to return.",
    )
    min_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold.",
    )


class CuratedFactSearchResponse(BaseModel):
    query: str = Field(
        ...,
        description="The submitted query.",
    )
    total_results: int = Field(
        ...,
        description="Total number of matching curated fact-check chunks returned.",
    )
    results: List[CuratedFactChunk] = Field(
        default_factory=list,
        description="Ranked list of curated fact-check chunks with verdict metadata.",
    )


class EvidenceItem(BaseModel):
    evidence_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for evidence item (e.g. 'ev_123').",
    )
    sub_claim_id: str = Field(
        ...,
        description="ID of the sub-claim this evidence was retrieved for.",
    )
    sub_claim: Optional[str] = Field(
        default="",
        description="The verbatim sub-claim text.",
    )
    quote: str = Field(
        ...,
        description="Verbatim quote from source.",
    )
    source_url: str = Field(
        ...,
        description="URL of source publication.",
    )
    domain: Optional[str] = Field(
        default="",
        description="Extracted domain (e.g. 'who.int', 'boomlive.in').",
    )
    domain_tier: Optional[int] = Field(
        default=2,
        description="Credibility tier: 1=Curated fact-checker, 2=Gov/Official, 3=Reputable news, 4=Web/Unverified.",
    )
    publish_date: Optional[str] = Field(
        default=None,
        description="Publication date of the evidence.",
    )
    retrieved_date: Optional[str] = Field(
        default=None,
        description="Timestamp when evidence was retrieved.",
    )
    retrieved_by: Optional[str] = Field(
        default="proponent",
        description="'proponent' or 'skeptic'.",
    )
    curated: bool = Field(
        default=False,
        description="True if retrieved from curated fact-check vector store.",
    )
    nli_label: Optional[str] = Field(
        default=None,
        description="Deterministic NLI label: 'SUPPORTS', 'REFUTES', or 'NEUTRAL'.",
    )
    nli_confidence: Optional[float] = Field(
        default=None,
        description="Softmax confidence score for the winning NLI label (0.0 to 1.0).",
    )
    nli_scores: Optional[Dict[str, float]] = Field(
        default=None,
        description="Full probability distribution over SUPPORTS, REFUTES, and NEUTRAL.",
    )


class NLIPairResult(BaseModel):
    sub_claim: str = Field(..., description="The sub-claim text.")
    quote: str = Field(..., description="The evidence quote text.")
    nli_label: str = Field(..., description="SUPPORTS, REFUTES, or NEUTRAL.")
    nli_confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    scores: Dict[str, float] = Field(default_factory=dict, description="Probabilities for each class.")


class NLIRequest(BaseModel):
    pairs: List[Dict[str, str]] = Field(
        ...,
        min_length=1,
        description="List of dicts with 'sub_claim' and 'quote' keys.",
    )


class NLIResponse(BaseModel):
    total_pairs: int = Field(..., description="Total pairs evaluated.")
    results: List[NLIPairResult] = Field(default_factory=list, description="List of NLI verification results.")


class SubClaimVerdict(BaseModel):
    sub_claim_id: str = Field(..., description="Unique sub-claim identifier.")
    sub_claim: str = Field(..., description="The sub-claim text.")
    score: float = Field(..., description="Calculated deterministic math score.")
    verdict: str = Field(..., description="TRUE, FALSE, PARTIALLY TRUE, or UNVERIFIED.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score.")
    evidence_count: int = Field(default=0, description="Total evidence items evaluated.")
    supporting_count: int = Field(default=0, description="Number of supporting items.")
    refuting_count: int = Field(default=0, description="Number of refuting items.")
    neutral_count: int = Field(default=0, description="Number of neutral items.")
    key_evidence: List[EvidenceItem] = Field(default_factory=list, description="Top evidence items.")


class JudgeVerdictRequest(BaseModel):
    raw_claim: str = Field(..., min_length=3, description="Original headline or composite claim.")
    sub_claims: List[SubClaim] = Field(..., min_length=1, description="Decomposed atomic sub-claims.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Labeled evidence items.")
    generate_explanation: bool = Field(default=True, description="Whether to invoke LLM narrator for 3-5 sentence explanation.")


class JudgeVerdictResponse(BaseModel):
    raw_claim: str = Field(..., description="Original claim text.")
    overall_verdict: str = Field(..., description="Aggregated verdict: TRUE, FALSE, PARTIALLY TRUE, or UNVERIFIED.")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated aggregated confidence.")
    overall_score: float = Field(..., description="Aggregated score.")
    is_abstained: bool = Field(default=False, description="True if system abstained (verdict is UNVERIFIED due to low evidence/confidence).")
    sub_claim_verdicts: List[SubClaimVerdict] = Field(default_factory=list, description="Per-sub-claim verdict breakdowns.")
    explanation: str = Field(default="", description="Narrative 3-5 sentence audit explanation citing quotes.")
    key_citations: List[str] = Field(default_factory=list, description="Key source URLs cited in justification.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="List of all evaluated evidence quotes with URLs, domain tiers, and NLI labels.")
    tokens_used: int = Field(default=0, description="Total LLM tokens utilized across decomposition and explanation.")

    def to_ui_dict(self) -> Dict[str, Any]:
        """Formats the response for dumb rendering by frontend UI without requiring any frontend business logic."""
        return {
            "claim": self.raw_claim,
            "verdict": self.overall_verdict,
            "confidence": round(self.overall_confidence, 4),
            "score": round(self.overall_score, 4),
            "is_abstained": self.is_abstained,
            "explanation": self.explanation,
            "key_citations": self.key_citations,
            "sub_claims": [
                {
                    "id": sc.sub_claim_id,
                    "text": sc.sub_claim,
                    "verdict": sc.verdict,
                    "confidence": round(sc.confidence, 4),
                    "score": round(sc.score, 4),
                    "evidence_count": sc.evidence_count,
                    "supporting_count": sc.supporting_count,
                    "refuting_count": sc.refuting_count,
                    "neutral_count": sc.neutral_count,
                }
                for sc in self.sub_claim_verdicts
            ],
            "evidence": [
                {
                    "evidence_id": ev.evidence_id,
                    "sub_claim_id": ev.sub_claim_id,
                    "sub_claim": ev.sub_claim,
                    "quote": ev.quote,
                    "source_url": ev.source_url,
                    "domain": ev.domain,
                    "domain_tier": ev.domain_tier,
                    "nli_label": ev.nli_label,
                    "nli_confidence": ev.nli_confidence,
                    "retrieved_by": ev.retrieved_by,
                    "curated": ev.curated,
                }
                for ev in self.evidence
            ],
        }


class VerifyClaimRequest(BaseModel):
    claim: Optional[str] = Field(
        default=None,
        description="Raw headline or claim to verify.",
    )
    text: Optional[str] = Field(
        default=None,
        description="Alternative alias for claim.",
    )
    generate_explanation: bool = Field(
        default=True,
        description="Whether to invoke the LLM narrator to generate a 3-5 sentence audit explanation.",
    )

    def resolved_claim(self) -> str:
        val = (self.claim or self.text or "").strip()
        if len(val) < 3:
            raise ValueError("Claim must be at least 3 characters long.")
        return val


class VerificationJobResponse(BaseModel):
    job_id: str = Field(
        ...,
        description="Unique verification job identifier.",
    )
    status: str = Field(
        ...,
        description="Current status of the job: 'pending', 'processing', 'completed', or 'failed'.",
    )
    stage: Optional[str] = Field(
        default=None,
        description="Detailed execution stage: 'queued', 'decomposing', 'harvesting_evidence', 'sanitizing', 'nli_verification', 'judge_evaluating', 'completed'.",
    )
    claim: str = Field(
        default="",
        description="The claim submitted for verification.",
    )
    created_at: str = Field(
        ...,
        description="Job submission timestamp (ISO 8601).",
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="Job completion timestamp (ISO 8601).",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Total execution latency in milliseconds.",
    )
    token_count: Optional[int] = Field(
        default=0,
        description="Total LLM tokens logged across decomposition and judge explanation.",
    )
    cached: bool = Field(
        default=False,
        description="True if response was served from cache in milliseconds.",
    )
    result: Optional[Union[Dict[str, Any], JudgeVerdictResponse]] = Field(
        default=None,
        description="Full verification result dictionary for UI rendering.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if the job failed.",
    )



