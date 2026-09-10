"""
LPDG Innovation Hub – Chunk 1 Exploration Script
=================================================
Usage:  python explore.py [data_dir]   (default: data)

Produces concise summaries of every supplied dataset.
Safe to re-run; does NOT write large files into the repository.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def separator(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def pct(series: pd.Series) -> pd.Series:
    """Percentage distribution, sorted descending."""
    vc = series.value_counts(dropna=False)
    return (vc / len(series) * 100).round(2)


def null_report(df: pd.DataFrame) -> pd.DataFrame:
    n = df.isnull().sum()
    p = (n / len(df) * 100).round(2)
    return pd.DataFrame({"null_count": n, "null_pct": p}).query("null_count > 0")


# ---------------------------------------------------------------------------
# 1. Telemetry
# ---------------------------------------------------------------------------

TELEMETRY_COLS_CORE = [
    "gateway_id", "ts_utc",
    "offline_duration_sec", "disconnection_cnt",
    "reboot_cnt", "reboot_duration_sec",
    "r_cnt_power_cycle", "r_cnt_reboot", "r_cnt_unknown",
    "avg_reboot_duration", "no_conn_importance", "reboot_importance",
]

TELEMETRY_COLS_NETWORK = [
    "gateway_id", "ts_utc",
    "snr", "rssi", "noise_floor",
    "connected_meters_cnt", "registered_meters_cnt",
    "channel_util", "pdr",
]


def explore_telemetry(data_dir: Path) -> pd.DataFrame:
    """Load telemetry partitions and run all checks. Returns the DataFrame."""
    separator("TELEMETRY (partitioned parquet)")
    pq_path = data_dir / "telemetry"
    if not pq_path.exists():
        print("  [SKIP] telemetry partition directory not found")
        return pd.DataFrame()

    # --- load core columns only to keep memory reasonable ---
    section("Loading core columns")
    try:
        tel = pd.read_parquet(pq_path, columns=TELEMETRY_COLS_CORE)
    except Exception as exc:
        print(f"  ERROR loading core columns: {exc}")
        return pd.DataFrame()

    tel["ts"] = pd.to_datetime(tel["ts_utc"], utc=True)
    tel = tel.drop(columns=["ts_utc"])
    tel = tel.sort_values(["gateway_id", "ts"])

    print(f"  Rows:     {len(tel):,}")
    print(f"  Columns:  {tel.shape[1]}")
    print(f"  Dtypes:\n{tel.dtypes}")

    # --- basic timestamp checks ---
    section("Timestamp coverage")
    ts_min = tel["ts"].min()
    ts_max = tel["ts"].max()
    print(f"  Min ts : {ts_min}")
    print(f"  Max ts : {ts_max}")
    hours_span = int((ts_max - ts_min).total_seconds() / 3600)
    print(f"  Hours in full span: {hours_span:,}")

    # --- gateway count ---
    section("Gateway count")
    n_gw = tel["gateway_id"].nunique()
    print(f"  Unique gateways: {n_gw}")

    # --- hourly grain check ---
    section("Hourly grain check (sample of 5 gateways)")
    sample_gws = tel["gateway_id"].unique()[:5]
    for gw in sample_gws:
        sub = tel[tel["gateway_id"] == gw]["ts"].sort_values()
        diffs = sub.diff().dropna().dt.total_seconds() / 3600
        pct_1h = (diffs == 1.0).mean() * 100
        print(f"  {gw}: {len(sub)} rows, {pct_1h:.1f}% 1-hour gaps")

    # --- duplicate gateway-hour pairs ---
    section("Duplicate gateway-hour pairs")
    dupes = tel.duplicated(subset=["gateway_id", "ts"]).sum()
    print(f"  Duplicate rows: {dupes:,}")

    # --- missing hours per gateway ---
    section("Missing-hour analysis (all gateways)")
    gw_groups = tel.groupby("gateway_id")["ts"]
    missing_stats = []
    for gw, times in gw_groups:
        times = times.sort_values().reset_index(drop=True)
        expected = pd.date_range(times.iloc[0], times.iloc[-1], freq="h", tz="UTC")
        missing = len(expected) - len(times)
        missing_stats.append({"gateway_id": gw, "rows": len(times),
                               "expected_hours": len(expected),
                               "missing_hours": missing,
                               "missing_pct": round(missing / max(len(expected), 1) * 100, 2)})
    miss_df = pd.DataFrame(missing_stats)
    print(f"  Gateways with missing hours: {(miss_df['missing_hours'] > 0).sum()} / {n_gw}")
    print(f"  Missing-hour stats:\n{miss_df['missing_hours'].describe()}")
    worst_miss = miss_df.sort_values("missing_pct", ascending=False).head(10)
    print(f"\n  Top-10 gateways with most missing hours:\n{worst_miss.to_string(index=False)}")

    # --- null report ---
    section("Null values in core columns")
    nulls = null_report(tel)
    if nulls.empty:
        print("  No nulls found.")
    else:
        print(nulls.to_string())

    # --- distributions of reliability / health fields ---
    HEALTH_COLS = [
        "offline_duration_sec", "disconnection_cnt",
        "reboot_cnt", "reboot_duration_sec",
        "r_cnt_power_cycle", "r_cnt_reboot", "r_cnt_unknown",
        "avg_reboot_duration", "no_conn_importance", "reboot_importance",
    ]
    section("Reliability / health field distributions")
    for col in HEALTH_COLS:
        if col not in tel.columns:
            print(f"  {col}: NOT FOUND")
            continue
        s = tel[col]
        zeros = (s == 0).sum()
        negs  = (s < 0).sum()
        print(f"\n  {col}")
        print(f"    non-null: {s.count():,}  zeros: {zeros:,} ({zeros/len(s)*100:.1f}%)  "
              f"negatives: {negs:,}")
        print(f"    {s.describe().round(4).to_string()}")

    # --- now load network / radio columns ---
    section("Network / radio indicators (SNR, RSSI, PDR …)")
    try:
        tel_net = pd.read_parquet(pq_path, columns=TELEMETRY_COLS_NETWORK)
        for col in ["snr", "rssi", "noise_floor", "channel_util", "pdr",
                    "connected_meters_cnt", "registered_meters_cnt"]:
            if col not in tel_net.columns:
                print(f"  {col}: NOT FOUND")
                continue
            s = tel_net[col]
            print(f"\n  {col}")
            print(f"    {s.describe().round(3).to_string()}")
    except Exception as exc:
        print(f"  WARNING: could not load network columns: {exc}")

    return tel


# ---------------------------------------------------------------------------
# 2. Telemetry sample (2025-08)
# ---------------------------------------------------------------------------

def explore_telemetry_sample(data_dir: Path) -> None:
    separator("TELEMETRY SAMPLE (telemetry_sample_2025-08.csv)")
    fp = data_dir / "telemetry_sample_2025-08.csv"
    if not fp.exists():
        print("  [SKIP] file not found")
        return

    sample = pd.read_csv(fp, nrows=0)  # schema only first
    all_cols = list(sample.columns)
    print(f"  Columns ({len(all_cols)}): {all_cols}")

    # load fully to inspect
    sample = pd.read_csv(fp)
    print(f"  Rows: {len(sample):,}")

    section("Null report")
    nulls = null_report(sample)
    if nulls.empty:
        print("  No nulls.")
    else:
        print(nulls.to_string())

    if "gateway_id" in sample.columns:
        print(f"\n  Unique gateways: {sample['gateway_id'].nunique()}")

    if "ts_utc" in sample.columns:
        ts = pd.to_datetime(sample["ts_utc"], utc=True)
        print(f"  ts range: {ts.min()} → {ts.max()}")


# ---------------------------------------------------------------------------
# 3. Gateway master
# ---------------------------------------------------------------------------

def explore_gateway_master(data_dir: Path) -> pd.DataFrame:
    separator("GATEWAY MASTER (gateway_master.csv)")
    fp = data_dir / "gateway_master.csv"
    if not fp.exists():
        print("  [SKIP] file not found")
        return pd.DataFrame()

    for enc in ["utf-8", "cp1252", "latin-1"]:
        try:
            gm = pd.read_csv(fp, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    print(f"  Rows: {len(gm):,}  Cols: {gm.shape[1]}")
    print(f"  Columns: {list(gm.columns)}")

    section("Null report")
    nulls = null_report(gm)
    if nulls.empty:
        print("  No nulls.")
    else:
        print(nulls.to_string())

    section("Duplicate gateway_id rows")
    if "gateway_id" in gm.columns:
        dupes = gm.duplicated(subset=["gateway_id"]).sum()
        print(f"  Duplicate gateway_id rows: {dupes}")

    section("Categorical distributions")
    cat_cols = [c for c in ["site_type", "region", "hardware_model",
                             "firmware_version", "antenna_type", "customer"]
                if c in gm.columns]
    for col in cat_cols:
        vc = pct(gm[col])
        print(f"\n  {col} (top values):")
        print(vc.head(10).to_string())

    section("Meters installed distribution")
    if "meters_installed" in gm.columns:
        print(gm["meters_installed"].describe().round(2).to_string())
        zeros = (gm["meters_installed"] == 0).sum()
        print(f"  Gateways with 0 meters installed: {zeros}")

    return gm


# ---------------------------------------------------------------------------
# 4. Meter read success
# ---------------------------------------------------------------------------

def explore_meter_read_success(data_dir: Path) -> pd.DataFrame:
    separator("METER READ SUCCESS (meter_read_success.csv)")
    fp = data_dir / "meter_read_success.csv"
    if not fp.exists():
        print("  [SKIP] file not found")
        return pd.DataFrame()

    mrs = pd.read_csv(fp)
    print(f"  Rows: {len(mrs):,}  Cols: {mrs.shape[1]}")
    print(f"  Columns: {list(mrs.columns)}")

    section("Null report")
    nulls = null_report(mrs)
    if nulls.empty:
        print("  No nulls.")
    else:
        print(nulls.to_string())

    if "week_start" in mrs.columns:
        mrs["week_start"] = pd.to_datetime(mrs["week_start"])
        print(f"\n  Week range: {mrs['week_start'].min()} → {mrs['week_start'].max()}")
        print(f"  Unique weeks: {mrs['week_start'].nunique()}")

    if "gateway_id" in mrs.columns:
        print(f"  Unique gateways: {mrs['gateway_id'].nunique()}")

    section("meters_expected distribution")
    if "meters_expected" in mrs.columns:
        print(mrs["meters_expected"].describe().round(2).to_string())

    section("meters_read distribution")
    if "meters_read" in mrs.columns:
        print(mrs["meters_read"].describe().round(2).to_string())

    # read-success rate
    section("Read-success rate (meters_read / meters_expected, zero-denominator safe)")
    if "meters_expected" in mrs.columns and "meters_read" in mrs.columns:
        mrs["read_rate"] = np.where(
            mrs["meters_expected"] > 0,
            mrs["meters_read"] / mrs["meters_expected"],
            np.nan
        )
        print(mrs["read_rate"].describe().round(4).to_string())
        low_rate = (mrs["read_rate"] < 0.9).sum()
        print(f"  Rows with read_rate < 90%: {low_rate:,} ({low_rate/len(mrs)*100:.1f}%)")
        impossible = (mrs["read_rate"] > 1.0).sum()
        print(f"  Rows with read_rate > 100% (impossible): {impossible}")

    section("Missing weeks (coverage check)")
    if "gateway_id" in mrs.columns and "week_start" in mrs.columns:
        all_weeks = mrs["week_start"].unique()
        all_gws   = mrs["gateway_id"].unique()
        full_idx  = pd.MultiIndex.from_product([all_gws, all_weeks],
                                                names=["gateway_id", "week_start"])
        actual_idx = pd.MultiIndex.from_frame(mrs[["gateway_id", "week_start"]])
        n_missing  = full_idx.difference(actual_idx).__len__()
        print(f"  Expected combos: {len(full_idx):,}  "
              f"Missing combos: {n_missing:,} ({n_missing/len(full_idx)*100:.1f}%)")

    return mrs


# ---------------------------------------------------------------------------
# 5. Field visits
# ---------------------------------------------------------------------------

def explore_field_visits(data_dir: Path) -> pd.DataFrame:
    separator("FIELD VISITS (field_visits.csv)")
    fp = data_dir / "field_visits.csv"
    if not fp.exists():
        print("  [SKIP] file not found")
        return pd.DataFrame()

    fv = pd.read_csv(fp)
    print(f"  Rows: {len(fv):,}  Cols: {fv.shape[1]}")
    print(f"  Columns: {list(fv.columns)}")

    section("Null report")
    nulls = null_report(fv)
    if nulls.empty:
        print("  No nulls.")
    else:
        print(nulls.to_string())

    if "gateway_id" in fv.columns:
        n_gw = fv["gateway_id"].nunique()
        print(f"\n  Unique gateways with visits: {n_gw}")
        vc = fv["gateway_id"].value_counts()
        print(f"  Visits per gateway:\n{vc.describe().to_string()}")
        print(f"  Top-10 frequently visited:\n{vc.head(10).to_string()}")

    section("Visit dates")
    date_col = next((c for c in fv.columns if "date" in c.lower()), None)
    if date_col:
        fv[date_col] = pd.to_datetime(fv[date_col])
        print(f"  Date range ({date_col}): {fv[date_col].min()} → {fv[date_col].max()}")
        print(f"  Unique dates: {fv[date_col].nunique()}")

    section("Outcomes / reasons / parts")
    for col in ["outcome", "reason", "parts_replaced", "visit_reason", "result"]:
        if col in fv.columns:
            print(f"\n  {col}:")
            print(pct(fv[col]).head(15).to_string())

    section("Technician hours")
    for col in ["technician_hours", "tech_hours", "duration_hours", "hours"]:
        if col in fv.columns:
            print(f"\n  {col}:\n{fv[col].describe().to_string()}")

    return fv


# ---------------------------------------------------------------------------
# 6. Engineer review
# ---------------------------------------------------------------------------

def explore_engineer_review(data_dir: Path) -> pd.DataFrame:
    separator("ENGINEER REVIEW (engineer_review_2026-02.xlsx)")
    fp = data_dir / "engineer_review_2026-02.xlsx"
    if not fp.exists():
        print("  [SKIP] file not found")
        return pd.DataFrame()

    er = pd.read_excel(fp)
    print(f"  Rows: {len(er):,}  Cols: {er.shape[1]}")
    print(f"  Columns: {list(er.columns)}")

    section("Null report")
    nulls = null_report(er)
    if nulls.empty:
        print("  No nulls.")
    else:
        print(nulls.to_string())

    section("Label distribution (Normal vs Schlecht)")
    label_col = next((c for c in er.columns
                      if any(k in c.lower() for k in ["label", "status", "review",
                                                       "schlecht", "normal", "rating"])),
                     None)
    if label_col:
        print(f"\n  Column: '{label_col}'")
        print(pct(er[label_col]).to_string())
    else:
        # try all object columns
        for c in er.select_dtypes(include="object").columns:
            print(f"\n  {c}:")
            print(pct(er[c]).to_string())

    if "gateway_id" in er.columns:
        print(f"\n  Unique gateways in review: {er['gateway_id'].nunique()}")

    return er


# ---------------------------------------------------------------------------
# 7. Cross-dataset linkage checks
# ---------------------------------------------------------------------------

def cross_dataset_checks(tel: pd.DataFrame, gm: pd.DataFrame,
                          mrs: pd.DataFrame, fv: pd.DataFrame,
                          er: pd.DataFrame) -> None:
    separator("CROSS-DATASET LINKAGE CHECKS")

    if tel.empty or gm.empty:
        print("  Skipping – one or more datasets not loaded.")
        return

    tel_gws = set(tel["gateway_id"].unique()) if "gateway_id" in tel.columns else set()
    gm_gws  = set(gm["gateway_id"].unique())  if "gateway_id" in gm.columns  else set()
    mrs_gws = set(mrs["gateway_id"].unique()) if "gateway_id" in mrs.columns else set()
    fv_gws  = set(fv["gateway_id"].unique())  if "gateway_id" in fv.columns  else set()
    er_gws  = set(er["gateway_id"].unique())  if "gateway_id" in er.columns  else set()

    print(f"  Gateways in telemetry:         {len(tel_gws):>4}")
    print(f"  Gateways in gateway_master:    {len(gm_gws):>4}")
    print(f"  Gateways in meter_read:        {len(mrs_gws):>4}")
    print(f"  Gateways in field_visits:      {len(fv_gws):>4}")
    print(f"  Gateways in engineer_review:   {len(er_gws):>4}")

    print(f"\n  In gateway_master but NOT telemetry: {len(gm_gws - tel_gws)}")
    print(f"  In telemetry but NOT gateway_master: {len(tel_gws - gm_gws)}")
    print(f"  In meter_read but NOT gateway_master: {len(mrs_gws - gm_gws)}")
    print(f"  In field_visits but NOT gateway_master: {len(fv_gws - gm_gws)}")
    print(f"  In engineer_review but NOT gateway_master: {len(er_gws - gm_gws)}")

    if gm_gws:
        fv_pct  = len(fv_gws & gm_gws) / len(gm_gws) * 100
        er_pct  = len(er_gws & gm_gws) / len(gm_gws) * 100
        mrs_pct = len(mrs_gws & gm_gws) / len(gm_gws) * 100
        print(f"\n  Coverage vs gateway_master:")
        print(f"    field_visits covers     : {fv_pct:.1f}% of gateways")
        print(f"    meter_read covers       : {mrs_pct:.1f}% of gateways")
        print(f"    engineer_review covers  : {er_pct:.1f}% of gateways")

    # Schlecht gateways vs field-visit history
    section("Schlecht gateways – field visit history")
    label_col = None
    schlecht_gws: set = set()
    if not er.empty:
        for c in er.columns:
            if er[c].dtype == object and er[c].str.lower().str.contains(
                    "schlecht", na=False).any():
                label_col = c
                break
        if label_col and "gateway_id" in er.columns:
            schlecht_gws = set(er.loc[er[label_col].str.lower() == "schlecht",
                                       "gateway_id"])
            normal_gws   = set(er.loc[er[label_col].str.lower() == "normal",
                                       "gateway_id"])
            print(f"  Schlecht gateways: {len(schlecht_gws)}")
            print(f"  Normal  gateways: {len(normal_gws)}")
            if fv_gws:
                s_visited = len(schlecht_gws & fv_gws)
                n_visited = len(normal_gws & fv_gws)
                print(f"  Schlecht with field visit history: "
                      f"{s_visited}/{len(schlecht_gws)} ({s_visited/max(len(schlecht_gws),1)*100:.0f}%)")
                print(f"  Normal  with field visit history: "
                      f"{n_visited}/{len(normal_gws)} ({n_visited/max(len(normal_gws),1)*100:.0f}%)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LPDG data exploration")
    parser.add_argument("data_dir", nargs="?", default="data",
                        help="Path to the data directory (default: data)")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"ERROR: data directory '{data_dir}' does not exist.")
        sys.exit(1)

    tel = explore_telemetry(data_dir)
    explore_telemetry_sample(data_dir)
    gm  = explore_gateway_master(data_dir)
    mrs = explore_meter_read_success(data_dir)
    fv  = explore_field_visits(data_dir)
    er  = explore_engineer_review(data_dir)
    cross_dataset_checks(tel, gm, mrs, fv, er)

    separator("EXPLORATION COMPLETE")


if __name__ == "__main__":
    main()
