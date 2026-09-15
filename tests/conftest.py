"""Global pytest fixtures and synthetic data setup for CI and unit tests.

The challenge dataset in root `data/` is strictly private and must not be published
or required in public CI environments. This module provides small synthetic fixtures
that satisfy schema contracts, test loaders, and exercise the API/service without
containing any real challenge data.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.lpdg.config.settings import SCORED_WEEKS, STRATEGY_V1
from src.services.ranking_service import RankingService


# Synthetic gateway identifiers (deterministic 12-char hex, fully synthetic)
SYNTHETIC_GATEWAYS = [
    "ABCDEF000001",
    "000000000001",
    "000000000002",
    "000000000003",
    "000000000004",
    "000000000005",
    "000000000006",
    "000000000007",
    "000000000008",
    "000000000009",
    "00000000000A",
    "00000000000B",
    "00000000000C",
    "00000000000D",
    "00000000000E",
    "00000000000F",
    "000000000010",
    "000000000011",
    "000000000012",
    "000000000013",
    "000000000014",
    "000000000015",
    "000000000016",
    "000000000017",
    "000000000018",
    "000000000099",  # Decommissioned gateway
]


@pytest.fixture(scope="session")
def synthetic_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a minimal synthetic data directory with master CSV and partitioned parquet telemetry.

    Contains 25 active synthetic gateways and 1 decommissioned gateway across the 8-week window.
    Zero rows or values are copied from the challenge dataset.
    """
    data_dir = tmp_path_factory.mktemp("synthetic_lpdg_data")

    # 1. Generate gateway_master.csv with realistic string dates
    decom_dates: list[str | None] = [None] * (len(SYNTHETIC_GATEWAYS) - 1) + ["2025-11-01"]
    master_df = pd.DataFrame(
        {
            "gateway_id": SYNTHETIC_GATEWAYS,
            "tenant": ["TENANT_A"] * len(SYNTHETIC_GATEWAYS),
            "site_type": ["RESIDENTIAL"] * len(SYNTHETIC_GATEWAYS),
            "region": ["REGION_1"] * len(SYNTHETIC_GATEWAYS),
            "hw_model": ["MODEL_X"] * len(SYNTHETIC_GATEWAYS),
            "antenna_type": ["INTERNAL"] * len(SYNTHETIC_GATEWAYS),
            "fw_version": ["1.0.0"] * len(SYNTHETIC_GATEWAYS),
            "fw_updated_on": ["2024-01-01"] * len(SYNTHETIC_GATEWAYS),
            "installed_on": ["2020-01-01"] * len(SYNTHETIC_GATEWAYS),
            "decommissioned_on": decom_dates,
            "n_meters_installed": [100 + i * 10 for i in range(len(SYNTHETIC_GATEWAYS))],
        }
    )
    master_df.to_csv(data_dir / "gateway_master.csv", index=False)

    # 2. Generate telemetry/ partitioned parquet directory
    telemetry_dir = data_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic hourly telemetry covering the scored weeks.
    timestamps = pd.date_range("2026-01-25", "2026-03-24", freq="h", tz="UTC")

    records: list[dict] = []
    # Primary gateway has impaired metrics to guarantee non-zero scores and reasons
    for ts in timestamps:
        # Partition 1: Primary test gateway
        records.append(
            {
                "gateway_id": "ABCDEF000001",
                "ts_utc": ts,
                "offline_duration_sec": 3600.0,
                "disconnection_cnt": 5.0,
                "reboot_cnt": 1.0,
                "no_conn_importance": 500.0,
            }
        )
        # Partition 2: Other gateways with varying synthetic impairments
        for i, gw in enumerate(SYNTHETIC_GATEWAYS[1:], start=1):
            records.append(
                {
                    "gateway_id": gw,
                    "ts_utc": ts,
                    "offline_duration_sec": float(i * 100),
                    "disconnection_cnt": float(i % 5),
                    "reboot_cnt": float(i % 2),
                    "no_conn_importance": float(i * 50),
                }
            )

    df_telemetry = pd.DataFrame(records)
    # Write to a single parquet or monthly chunks
    df_telemetry.to_parquet(telemetry_dir / "synthetic_part.parquet", index=False)

    return data_dir


@pytest.fixture
def synthetic_service(synthetic_data_dir: Path) -> RankingService:
    """Instantiate a RankingService bound to the synthetic test data."""
    return RankingService(strategy=STRATEGY_V1, data_dir=synthetic_data_dir)


@pytest.fixture
def synthetic_client(synthetic_service: RankingService) -> Generator[TestClient, None, None]:
    """FastAPI TestClient using the synthetic data service."""
    app = create_app(service=synthetic_service)
    yield TestClient(app)
