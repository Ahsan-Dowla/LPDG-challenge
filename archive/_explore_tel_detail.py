import pandas as pd, numpy as np

# ---- Telemetry duplicate analysis ----
tel = pd.read_parquet('data/telemetry', columns=[
    'gateway_id', 'ts_utc', 'offline_duration_sec', 'disconnection_cnt',
    'reboot_cnt', 'month'])
tel['ts'] = pd.to_datetime(tel['ts_utc'], utc=True)

print('Total rows:', len(tel))
print('Duplicate gateway+ts rows:', tel.duplicated(subset=['gateway_id', 'ts']).sum())
print()

# Show some duplicates
dupes = tel[tel.duplicated(subset=['gateway_id', 'ts'], keep=False)].sort_values(['gateway_id','ts'])
print('Sample duplicated records (first 20):')
print(dupes[['gateway_id', 'ts_utc', 'offline_duration_sec', 'disconnection_cnt', 'reboot_cnt', 'month']].head(20).to_string())
print()

# Are the duplicates exact copies or conflicting values?
dup_gw_ts = dupes.groupby(['gateway_id', 'ts_utc'])
n_conflicts = 0
n_exact = 0
for (gw, ts), grp in dup_gw_ts:
    if len(grp) > 1:
        if grp[['offline_duration_sec','disconnection_cnt','reboot_cnt']].nunique().max() > 1:
            n_conflicts += 1
        else:
            n_exact += 1
print(f'Duplicate pairs: exact copies={n_exact}, conflicting values={n_conflicts}')
print()

# Are duplicates from same month partition or cross-partition?
dup_months = dupes.groupby(['gateway_id','ts_utc'])['month'].nunique()
cross_partition = (dup_months > 1).sum()
print(f'Duplicate pairs crossing month partitions: {cross_partition}')
print()

# Telemetry sample (August 2025) column check
sample = pd.read_csv('data/telemetry_sample_2025-08.csv', nrows=5)
print('TELEMETRY SAMPLE COLUMNS:')
print(list(sample.columns))
print()

sample_full = pd.read_csv('data/telemetry_sample_2025-08.csv')
print(f'Sample rows: {len(sample_full)}  unique gateways: {sample_full["gateway_id"].nunique() if "gateway_id" in sample_full.columns else "N/A"}')
ts_col = next((c for c in sample_full.columns if 'ts' in c.lower() or 'time' in c.lower()), None)
if ts_col:
    ts = pd.to_datetime(sample_full[ts_col], utc=True, errors='coerce')
    print(f'  ts range: {ts.min()} -> {ts.max()}')

# null check for sample
n = sample_full.isnull().sum()
ndf = pd.DataFrame({'null_count': n, 'null_pct': (n/len(sample_full)*100).round(2)}).query('null_count>0')
print('NULLS in sample:')
print(ndf.to_string() if not ndf.empty else 'None')
print()

# Telemetry: counter behaviour - are reboot counters ever >24 in a single hour?
tel2 = pd.read_parquet('data/telemetry', columns=[
    'gateway_id', 'ts_utc',
    'reboot_cnt', 'r_cnt_power_cycle', 'r_cnt_reboot', 'r_cnt_unknown',
    'disconnection_cnt'])

print('Suspicious counter values (per-hour):')
print(f'  reboot_cnt > 5: {(tel2["reboot_cnt"] > 5).sum()}')
print(f'  reboot_cnt > 10: {(tel2["reboot_cnt"] > 10).sum()}')
print(f'  disconnection_cnt > 10: {(tel2["disconnection_cnt"] > 10).sum()}')
print(f'  r_cnt_power_cycle > 5: {(tel2["r_cnt_power_cycle"] > 5).sum()}')
max_reboot = tel2["reboot_cnt"].max()
max_disc   = tel2["disconnection_cnt"].max()
print(f'  max reboot_cnt in one hour: {max_reboot}')
print(f'  max disconnection_cnt in one hour: {max_disc}')
print()

# offline_duration_sec > 3600 (impossible for a single hour)
tel3 = pd.read_parquet('data/telemetry', columns=['gateway_id', 'ts_utc', 'offline_duration_sec'])
impossible_offline = (tel3['offline_duration_sec'] > 3600).sum()
print(f'offline_duration_sec > 3600 (impossible for 1-hour window): {impossible_offline}')
extreme_offline = tel3[tel3['offline_duration_sec'] > 3600]
print('Sample extreme offline_duration_sec rows:')
print(extreme_offline.sort_values('offline_duration_sec', ascending=False).head(10).to_string())

print()
print('DONE')
