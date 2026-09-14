"""Central domain exceptions for the LPDG package."""

from __future__ import annotations


class LPDGError(Exception):
    """Base exception for all LPDG domain and pipeline errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = str(message)


class DataNotFoundError(LPDGError):
    """Raised when required data directories or files are missing."""


class InvalidWeekError(LPDGError):
    """Raised when an unparseable or out-of-window week date is requested."""


class GatewayNotFoundError(LPDGError):
    """Raised when an explanation is requested for an unknown or unranked gateway."""


class InvalidStrategyError(LPDGError):
    """Raised when an unknown ranking strategy is requested."""


class PipelineExecutionError(LPDGError):
    """Raised when an internal error occurs during ranking or prediction execution."""
