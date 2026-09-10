"""Custom exceptions for the ranking service layer."""

from __future__ import annotations


class RankingServiceError(Exception):
    """Base exception for all service layer errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GatewayNotFoundError(RankingServiceError):
    """Raised when a gateway ID is not found or has no active data in the evaluated window."""


class InvalidWeekError(RankingServiceError):
    """Raised when an invalid or out-of-window week date is requested."""


class DataNotFoundError(RankingServiceError):
    """Raised when required telemetry or master data files cannot be located."""


class PipelineExecutionError(RankingServiceError):
    """Raised when the ranking pipeline encounters an internal failure during calculation."""
