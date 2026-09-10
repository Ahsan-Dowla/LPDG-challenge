"""API route handlers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from src.services.ranking_service import RankingService

from .schemas import (
    GatewayExplanationResponse,
    HealthResponse,
    PredictRequest,
    PredictResponse,
    WeeklyPredictionResponse,
)

router = APIRouter()


def get_service(request: Request) -> RankingService:
    """Retrieve RankingService instance from application state."""
    service = getattr(request.app.state, "ranking_service", None)
    if service is None:
        service = RankingService()
        request.app.state.ranking_service = service
    return service


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns lightweight service status without executing expensive pipelines.",
)
def health_check(
    service: Annotated[RankingService, Depends(get_service)],
) -> HealthResponse:
    return HealthResponse(**service.get_health())


@router.get(
    "/predictions/{week}",
    response_model=WeeklyPredictionResponse,
    summary="Get weekly gateway visit recommendations",
    description="Returns exactly 15 ranked gateways for a valid prediction week.",
)
def get_predictions(
    week: str,
    service: Annotated[RankingService, Depends(get_service)],
) -> WeeklyPredictionResponse:
    result = service.get_predictions_for_week(week)
    return WeeklyPredictionResponse(**result)


@router.get(
    "/gateways/{gateway_id}",
    response_model=GatewayExplanationResponse,
    summary="Explain gateway ranking",
    description="Explains why a gateway is ranked at its position for the specified or latest scored week.",
)
def explain_gateway(
    gateway_id: str,
    service: Annotated[RankingService, Depends(get_service)],
    week: str | None = Query(
        default=None,
        description="Optional Monday cutoff (YYYY-MM-DD). Defaults to the latest scored week.",
    ),
) -> GatewayExplanationResponse:
    result = service.explain_gateway(gateway_id=gateway_id, week_input=week)
    return GatewayExplanationResponse(**result)


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Trigger prediction rerun",
    description="Explicitly reruns the prediction pipeline for a single week or all scored weeks.",
)
def trigger_predict(
    service: Annotated[RankingService, Depends(get_service)],
    payload: PredictRequest | None = None,
) -> PredictResponse:
    week_start = payload.week_start if payload else None
    output_path = payload.output_path if payload else None
    result = service.run_prediction(week_start=week_start, output_path=output_path)
    return PredictResponse(**result)
