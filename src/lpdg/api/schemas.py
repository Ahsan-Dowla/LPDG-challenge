"""Pydantic schemas for the LPDG Gateway Prioritization REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Lightweight operational health response."""
    model_config = ConfigDict(extra="forbid")
    status: str = Field(..., description="System operational status, e.g. 'ok'")


class PredictionItem(BaseModel):
    """A single gateway visit prediction recommendation."""
    model_config = ConfigDict(extra="forbid")
    week_start: str = Field(..., description="Scored Monday cutoff date (YYYY-MM-DD)")
    rank: int = Field(..., ge=1, le=15, description="Priority rank 1 to 15 within the week")
    gateway_id: str = Field(..., description="12-character uppercase hexadecimal gateway ID")
    score: float = Field(..., description="Evidence or expected-value priority score")
    reason: str = Field(..., max_length=300, description="Concise operational reason for site visit")


class PredictionsResponse(BaseModel):
    """Top-15 gateway visit recommendations for a specific week."""
    model_config = ConfigDict(extra="forbid")
    week_start: str = Field(..., description="Prediction Monday cutoff date (YYYY-MM-DD)")
    count: int = Field(..., description="Number of recommendations returned (always 15)")
    predictions: list[PredictionItem] = Field(..., description="Ordered list of recommended visits")


class PredictionRunRequest(BaseModel):
    """Request payload to trigger prediction pipeline rerun."""
    model_config = ConfigDict(extra="forbid")
    week_start: str | None = Field(
        default=None,
        description="Optional single Monday cutoff (YYYY-MM-DD). If omitted, runs all 8 scored weeks.",
    )
    output_path: str | None = Field(
        default=None,
        description="Optional destination file path to save predictions CSV",
    )
    strategy: str | None = Field(
        default=None,
        description="Optional ranking strategy override: 'v1', 'v2', or 'baseline'",
    )


class PredictionRunResponse(BaseModel):
    """Response payload following prediction execution."""
    model_config = ConfigDict(extra="forbid")
    status: str = Field(..., description="Execution status, e.g. 'success'")
    strategy: str = Field(..., description="Ranking strategy executed")
    weeks_predicted: list[str] = Field(..., description="List of week cutoffs processed")
    total_predictions: int = Field(..., description="Total rows generated")
    output_path: str | None = Field(default=None, description="File path where predictions were saved, if requested")
    predictions: list[PredictionItem] = Field(..., description="Generated prediction records")


class GatewayExplanationResponse(BaseModel):
    """Detailed operational explanation for a gateway's ranking."""
    model_config = ConfigDict(extra="forbid")
    gateway_id: str = Field(..., description="Normalized 12-character hex gateway ID")
    week_start: str = Field(..., description="Scored Monday cutoff date (YYYY-MM-DD)")
    rank: int | None = Field(default=None, description="Top-15 rank if selected for a visit, else null")
    overall_rank: int = Field(..., description="Position in the full ranked active gateway pool")
    score: float = Field(..., description="Priority score")
    reason: str = Field(..., description="Concise operational explanation string")
    details: dict[str, Any] = Field(..., description="Supporting operational telemetry metrics and signals")


class ErrorResponse(BaseModel):
    """Structured error response payload."""
    model_config = ConfigDict(extra="forbid")
    detail: str = Field(..., description="Human-readable error description")
