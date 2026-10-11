from typing import List, Optional, Union
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
