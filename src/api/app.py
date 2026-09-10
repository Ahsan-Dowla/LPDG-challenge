"""FastAPI application factory and centralized error handling."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.services.exceptions import (
    DataNotFoundError,
    GatewayNotFoundError,
    InvalidWeekError,
    PipelineExecutionError,
    RankingServiceError,
)
from src.services.ranking_service import RankingService

from .routes import router

logger = logging.getLogger("gateway_api")


def create_app(service: RankingService | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="LPDG Gateway Ranking API",
        description="Operational API for weekly smart meter gateway visit prioritization.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    if service is None:
        service = RankingService()
    application.state.ranking_service = service

    application.include_router(router)

    @application.exception_handler(GatewayNotFoundError)
    async def gateway_not_found_handler(
        request: Request, exc: GatewayNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.message},
        )

    @application.exception_handler(InvalidWeekError)
    async def invalid_week_handler(
        request: Request, exc: InvalidWeekError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )

    @application.exception_handler(DataNotFoundError)
    async def data_not_found_handler(
        request: Request, exc: DataNotFoundError
    ) -> JSONResponse:
        logger.error(f"Data missing: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Required challenge data is unavailable or missing."},
        )

    @application.exception_handler(PipelineExecutionError)
    async def pipeline_error_handler(
        request: Request, exc: PipelineExecutionError
    ) -> JSONResponse:
        logger.error(f"Pipeline error: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Ranking pipeline failed: {exc.message}"},
        )

    @application.exception_handler(RankingServiceError)
    async def ranking_service_error_handler(
        request: Request, exc: RankingServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        message = errors[0].get("msg", "Validation error") if errors else "Malformed request."
        return JSONResponse(
            status_code=422,
            content={"detail": f"Request validation failed: {message}"},
        )

    @application.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(f"Unhandled server error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred while processing the request."},
        )

    return application


app = create_app()
