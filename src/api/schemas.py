"""Pydantic schemas for API request and response validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health status response."""

    model_config = ConfigDict(extra="forbid")
    status: str = Field(..., examples=["ok"])


class PredictionItem(BaseModel):
    """Individual gateway visit recommendation."""

    model_config = ConfigDict(extra="forbid")
    week_start: str = Field(..., description="Monday prediction cutoff in YYYY-MM-DD format")
    rank: int = Field(..., ge=1, le=15, description="Visit priority rank from 1 to 15")
    gateway_id: str = Field(..., description="Canonical compact 12-char hex gateway identifier")
    score: float = Field(..., description="Evidence-based priority score")
    reason: str = Field(..., max_length=300, description="Operational explanation under 300 chars")


class WeeklyPredictionResponse(BaseModel):
    """Response payload for weekly predictions."""

    model_config = ConfigDict(extra="forbid")
    week_start: str
    count: int
    predictions: list[PredictionItem]


class GatewayDetails(BaseModel):
    """Detailed telemetry and operational metrics supporting gateway rank."""

    model_config = ConfigDict(extra="allow")
    coverage_hours: int = Field(..., description="Observed hours in recent window")
    problem_hours: int = Field(..., description="Hours with offline duration or disconnections")
    silent_hours: int = Field(..., description="Missing reporting hours out of expected 168h")
    expected_hours: int = Field(168, description="Expected reporting hours per week")
    worst_signal: str = Field(..., description="Primary telemetry signal breach")
    n_meters_installed: int = Field(..., description="Number of customer meters exposed")
    persistence_pct: int = Field(..., description="Calculated persistence percentage [0, 100]")


class GatewayExplanationResponse(BaseModel):
    """Explanation of why a gateway is ranked at its position."""

    model_config = ConfigDict(extra="forbid")
    gateway_id: str
    week_start: str
    rank: int | None = Field(None, description="Top-15 rank, or None if outside top 15")
    overall_rank: int = Field(..., description="Position in overall evaluated active gateway pool")
    score: float
    reason: str
    details: GatewayDetails


class PredictRequest(BaseModel):
    """Optional payload to trigger prediction rerun."""

    model_config = ConfigDict(extra="forbid")
    week_start: str | None = Field(
        None,
        description="Optional specific Monday cutoff (YYYY-MM-DD). If omitted, runs all scored weeks.",
    )
    output_path: str | None = Field(
        None,
        description="Optional filesystem path to write output CSV.",
    )


class PredictResponse(BaseModel):
    """Summary of prediction rerun execution."""

    model_config = ConfigDict(extra="forbid")
    status: str
    strategy: str
    weeks_predicted: list[str]
    total_predictions: int
    output_path: str | None = None
    predictions: list[PredictionItem] | None = None


class ErrorResponse(BaseModel):
    """Standardized error response payload."""

    model_config = ConfigDict(extra="forbid")
    detail: str
