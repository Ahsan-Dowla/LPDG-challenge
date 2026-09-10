from __future__ import annotations

import datetime as dt

import pandas as pd

from src.part1 import data_loader
from src.part1.data_loader import normalize_gateway_id
from src.part1.eligibility import active_gateways
from src.part1.config import OUTPUT_COLUMNS
from src.part1.ranker import build_predictions, rank_week


def telemetry_rows(gateway_id: str, timestamps: list[str], value: float = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gateway_id": gateway_id,
            "ts": pd.to_datetime(timestamps, utc=True),
            "offline_duration_sec": value,
            "disconnection_cnt": value,
            "reboot_cnt": value,
        }
    )


def test_gateway_ids_normalize_across_formats() -> None:
    assert normalize_gateway_id("02:02:cb:0a:6b:1f") == "0202CB0A6B1F"
    assert normalize_gateway_id(" 0202cb0a6b1f ") == "0202CB0A6B1F"


def test_rank_week_uses_only_rows_before_monday() -> None:
    frame = pd.concat(
        [
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"]),
            telemetry_rows("AAA", ["2026-02-02T00:00:00Z"], value=999),
        ],
        ignore_index=True,
    )
    ranked = rank_week(frame, dt.date(2026, 2, 2))
    assert ranked.iloc[0]["coverage_hours"] == 1
    assert ranked.iloc[0]["flagged_hours"] == 0


def test_duplicate_hour_is_removed_by_loader(monkeypatch, tmp_path) -> None:
    frame = telemetry_rows(
        "AAA",
        ["2026-01-26T00:00:00Z", "2026-01-27T00:00:00Z", "2026-01-28T00:00:00Z"],
        value=0,
    )
    duplicate = frame.iloc[[2]].copy()
    with_duplicate = pd.concat([frame, duplicate], ignore_index=True).rename(
        columns={"ts": "ts_utc"}
    )
    monkeypatch.setattr(data_loader.pd, "read_parquet", lambda *args, **kwargs: with_duplicate)
    loaded = data_loader.load_telemetry(tmp_path)
    assert len(loaded) == 3
    assert loaded["ts"].nunique() == 3


def test_decommissioned_gateway_is_ineligible_at_cutoff() -> None:
    master = pd.DataFrame(
        {
            "gateway_id": ["ACTIVE", "RETIRED", "FUTURE"],
            "installed_on": [dt.date(2020, 1, 1)] * 3,
            "decommissioned_on": [None, dt.date(2026, 2, 2), None],
        }
    )
    master.loc[2, "installed_on"] = dt.date(2026, 2, 3)
    assert active_gateways(master, dt.date(2026, 2, 2)) == {"ACTIVE"}


def test_ties_are_sorted_by_gateway_id() -> None:
    frame = pd.concat(
        [
            telemetry_rows("ZZZ", ["2026-01-31T23:00:00Z"]),
            telemetry_rows("AAA", ["2026-01-31T23:00:00Z"]),
        ],
        ignore_index=True,
    )
    ranked = rank_week(frame, dt.date(2026, 2, 2))
    assert ranked["gateway_id"].tolist() == ["AAA", "ZZZ"]


def test_build_predictions_has_required_weekly_shape() -> None:
    gateways = [f"{index:012X}" for index in range(15)]
    timestamps = pd.date_range("2026-01-01", "2026-03-23", freq="D", tz="UTC")
    rows = []
    for gateway_id in gateways:
        for timestamp in timestamps:
            rows.append(
                {
                    "gateway_id": gateway_id,
                    "ts": timestamp,
                    "offline_duration_sec": 0,
                    "disconnection_cnt": 0,
                    "reboot_cnt": 0,
                }
            )
    telemetry = pd.DataFrame(rows)
    master = pd.DataFrame(
        {
            "gateway_id": gateways,
            "installed_on": [dt.date(2020, 1, 1)] * 15,
            "decommissioned_on": [None] * 15,
        }
    )

    predictions = build_predictions(telemetry, master)

    assert predictions.columns.tolist() == OUTPUT_COLUMNS
    assert len(predictions) == 120
    assert predictions.groupby("week_start").size().tolist() == [15] * 8
    assert predictions.groupby("week_start")["rank"].apply(list).tolist() == [list(range(1, 16))] * 8
