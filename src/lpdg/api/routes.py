"""FastAPI route definitions for LPDG Gateway Prioritization."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.lpdg.ranking.service import RankingService

from .schemas import (
    ErrorResponse,
    GatewayExplanationResponse,
    HealthResponse,
    PredictionRunRequest,
    PredictionRunResponse,
    PredictionsResponse,
)

router = APIRouter()


def get_service() -> RankingService:
    """Dependency provider placeholder overridden at app factory instantiation."""
    raise NotImplementedError("RankingService dependency not injected.")


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Service Health Check",
    description="Returns operational health status and active default ranking strategy.",
)
def health_check(
    service: Annotated[RankingService, Depends(get_service)],
) -> HealthResponse:
    return HealthResponse(**service.get_health())


@router.get(
    "/predictions/{week}",
    response_model=PredictionsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid date format or unscored prediction week"},
        500: {"model": ErrorResponse, "description": "Pipeline execution error or missing data"},
    },
    summary="Get Weekly Recommendations",
    description="Retrieve the 15 prioritized gateway visits for a specific Monday cutoff date.",
)
def get_predictions_for_week(
    week: str,
    service: Annotated[RankingService, Depends(get_service)],
) -> PredictionsResponse:
    result = service.get_predictions_for_week(week)
    return PredictionsResponse(**result)


@router.get(
    "/gateways/{gateway_id}",
    response_model=GatewayExplanationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid week or parameters"},
        404: {"model": ErrorResponse, "description": "Gateway not found in active set for the week"},
        500: {"model": ErrorResponse, "description": "Internal calculation error"},
    },
    summary="Explain Gateway Ranking",
    description="Inspect why a gateway is ranked at its position with supporting operational telemetry metrics.",
)
def explain_gateway(
    gateway_id: str,
    service: Annotated[RankingService, Depends(get_service)],
    week: Annotated[
        str | None,
        Query(description="Scored Monday cutoff date (YYYY-MM-DD). Defaults to latest scored week."),
    ] = None,
) -> GatewayExplanationResponse:
    explanation = service.explain_gateway(gateway_id, week)
    return GatewayExplanationResponse(**explanation)


@router.post(
    "/predict",
    response_model=PredictionRunResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameter or unscored week"},
        422: {"model": ErrorResponse, "description": "Malformed schema or unexpected fields"},
        500: {"model": ErrorResponse, "description": "Pipeline execution failure"},
    },
    summary="Trigger Prediction Rerun",
    description="Explicitly execute ranking for a single week or all 8 scored weeks, optionally saving to disk.",
)
def trigger_prediction(
    request: PredictionRunRequest,
    service: Annotated[RankingService, Depends(get_service)],
) -> PredictionRunResponse:
    # If strategy override is requested, switch strategy temporarily or execute accordingly
    current_strategy = service.strategy.name
    try:
        if request.strategy:
            service.set_strategy(request.strategy)
        result = service.run_prediction(
            week_start=request.week_start,
            output_path=request.output_path,
        )
        return PredictionRunResponse(**result)
    finally:
        if request.strategy and service.strategy.name != current_strategy:
            service.set_strategy(current_strategy)
