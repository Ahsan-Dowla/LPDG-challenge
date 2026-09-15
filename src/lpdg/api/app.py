"""FastAPI application factory and exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.lpdg.exceptions import (
    DataNotFoundError,
    GatewayNotFoundError,
    InvalidStrategyError,
    InvalidWeekError,
    PipelineExecutionError,
)
from src.lpdg.ranking.service import RankingService

from .routes import get_service, router

logger = logging.getLogger("lpdg.api")


def create_app(service: RankingService | None = None) -> FastAPI:
    """Create and configure the FastAPI web application instance."""
    app = FastAPI(
        title="LPDG Gateway Prioritization API",
        version="2.0.0",
        description=(
            "REST API providing weekly smart-meter gateway visit prioritization, "
            "operational explanation, and prediction pipeline execution."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    ranking_service = service if service is not None else RankingService()
    app.dependency_overrides[get_service] = lambda: ranking_service
    app.state.service = ranking_service

    @app.exception_handler(InvalidWeekError)
    async def invalid_week_handler(request: Request, exc: InvalidWeekError) -> JSONResponse:
        logger.warning("Invalid week request (%s): %s", request.url.path, exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidStrategyError)
    async def invalid_strategy_handler(request: Request, exc: InvalidStrategyError) -> JSONResponse:
        logger.warning("Invalid strategy request (%s): %s", request.url.path, exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(GatewayNotFoundError)
    async def gateway_not_found_handler(request: Request, exc: GatewayNotFoundError) -> JSONResponse:
        logger.info("Gateway not found (%s): %s", request.url.path, exc)
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DataNotFoundError)
    async def data_not_found_handler(request: Request, exc: DataNotFoundError) -> JSONResponse:
        logger.error("Data error encountered (%s): %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Required data unavailable: {exc}"},
        )

    @app.exception_handler(PipelineExecutionError)
    async def pipeline_error_handler(request: Request, exc: PipelineExecutionError) -> JSONResponse:
        logger.error("Ranking pipeline failure (%s): %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Ranking pipeline failed: {exc}"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Request schema validation failed (%s): %s", request.url.path, exc)
        error_msgs = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": f"Request validation failed: {'; '.join(error_msgs)}"},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.critical("Unhandled server exception (%s): %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred while processing the request."},
        )

    app.include_router(router)
    return app


# Default singleton app for ASGI servers (e.g. uvicorn src.lpdg.api.app:app)
app = create_app()
