"""Pydantic schemas for the Tarang Pharma receipt review API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class DecisionRequest(BaseModel):
    claim: dict[str, Any] = Field(
        ..., description="Claim record including claim ID, category, amount and employee ID"
    )
    receipt: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted receipt fields; use empty values for unavailable fields",
    )
    employee: dict[str, Any] = Field(
        default_factory=dict, description="Employee record, when available"
    )
    receipt_available: bool = True
    duplicate_info: dict[str, Any] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    claim_id: str = ""
    decision: Literal["approve", "review"]
    reason: str
    reasons: list[str] = Field(default_factory=list)
    vendor: str = ""
    total_amount: Any = None
    duplicate_detected: bool = False
    possible_matches: list[Any] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
