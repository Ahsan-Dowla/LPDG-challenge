import pandas as pd

METRICS = [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]

telemetry = pd.read_parquet(
    "data/telemetry",
    columns=["gateway_id", "ts_utc", *METRICS]
)

telemetry["ts"] = pd.to_datetime(
    telemetry["ts_utc"],
    utc=True
)

telemetry = telemetry.drop(columns=["ts_utc"])

print(telemetry.shape)
print(telemetry.head())
print(telemetry.dtypes)
