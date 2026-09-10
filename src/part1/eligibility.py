from __future__ import annotations

import datetime as dt

import pandas as pd


def active_gateways(master: pd.DataFrame, cutoff: dt.date) -> set[str]:
    """Return gateways in service at Monday 00:00 UTC.

    A missing installation date is treated as unknown but eligible; a known
    installation after the cutoff is not yet active. A decommission date on or
    before the cutoff means the gateway is no longer eligible.
    """
    installed = master["installed_on"].isna() | (master["installed_on"] <= cutoff)
    decommissioned = master["decommissioned_on"].notna() & (
        master["decommissioned_on"] <= cutoff
    )
    return set(master.loc[installed & ~decommissioned, "gateway_id"])


def eligible_telemetry(
    telemetry: pd.DataFrame, master: pd.DataFrame, cutoff: dt.date
) -> pd.DataFrame:
    """Keep only telemetry belonging to gateways active at the prediction cutoff."""
    eligible = active_gateways(master, cutoff)
    return telemetry[telemetry["gateway_id"].isin(eligible)].copy()
