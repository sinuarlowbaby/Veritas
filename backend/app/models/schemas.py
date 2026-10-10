from typing import List
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
