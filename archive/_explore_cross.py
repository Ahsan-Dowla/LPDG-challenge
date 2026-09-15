import pandas as pd, numpy as np

# ---- Cross-dataset analysis ----
# 1. Gateway ID format normalization check

# Load all datasets
gm = None
for enc in ['utf-8', 'cp1252', 'latin-1']:
    try:
        gm = pd.read_csv('data/gateway_master.csv', encoding=enc)
        break
    except UnicodeDecodeError:
        continue

mrs = pd.read_csv('data/meter_read_success.csv')
fv  = pd.read_csv('data/field_visits.csv')
import openpyxl
er  = pd.read_excel('data/engineer_review_2026-02.xlsx')
tel = pd.read_parquet('data/telemetry', columns=['gateway_id'])

# Sample of IDs from each
print('=== GATEWAY ID FORMAT SAMPLES ===')
print('telemetry:', tel['gateway_id'].iloc[:5].tolist())
print('gateway_master:', gm['gateway_id'].iloc[:5].tolist())
print('meter_read_success:', mrs['gateway_id'].iloc[:5].tolist())
print('field_visits:', fv['gateway_id'].iloc[:5].tolist())
print('engineer_review:', er['gateway_id'].iloc[:5].tolist())
print()

# Normalize all to compact uppercase HEX (no separators)
def normalize_gw(s):
    return s.str.upper().str.replace(':', '', regex=False).str.replace('-', '', regex=False).str.strip()

tel_gws = set(normalize_gw(tel['gateway_id'].drop_duplicates()))
gm_gws  = set(normalize_gw(gm['gateway_id']))
mrs_gws = set(normalize_gw(mrs['gateway_id'].drop_duplicates()))
fv_gws  = set(normalize_gw(fv['gateway_id'].drop_duplicates()))
er_gws  = set(normalize_gw(er['gateway_id'].drop_duplicates()))

print('=== GATEWAY COUNTS (normalized) ===')
print(f'telemetry:         {len(tel_gws):>4}')
print(f'gateway_master:    {len(gm_gws):>4}')
print(f'meter_read_success:{len(mrs_gws):>4}')
print(f'field_visits:      {len(fv_gws):>4}')
print(f'engineer_review:   {len(er_gws):>4}')
print()

print('=== CROSS-DATASET MISMATCHES (normalized) ===')
print(f'gm - tel (in master, not in telemetry): {len(gm_gws - tel_gws)}')
print(f'tel - gm (in telemetry, not in master): {len(tel_gws - gm_gws)}')
print(f'mrs - gm: {len(mrs_gws - gm_gws)}')
print(f'fv - gm:  {len(fv_gws - gm_gws)}')
print(f'er - gm:  {len(er_gws - gm_gws)}')
print()

# IDs that are in master but not telemetry
orphan_master = gm_gws - tel_gws
print(f'In gateway_master but NOT telemetry: {sorted(orphan_master)}')
orphan_tel = tel_gws - gm_gws
print(f'In telemetry but NOT gateway_master: {sorted(orphan_tel)}')
print()

# Schlecht vs Normal - field visit history
er['gw_norm'] = normalize_gw(er['gateway_id'])
fv_norm = set(normalize_gw(fv['gateway_id'].drop_duplicates()))

label_col = 'Kategorie'
schlecht = set(er[er[label_col].str.lower() == 'schlecht']['gw_norm'])
normal   = set(er[er[label_col].str.lower() == 'normal']['gw_norm'])

print('=== ENGINEER REVIEW vs FIELD VISITS ===')
s_vis = len(schlecht & fv_norm)
n_vis = len(normal & fv_norm)
print(f'Schlecht ({len(schlecht)}) with field visit history: {s_vis} ({s_vis/len(schlecht)*100:.0f}%)')
print(f'Normal   ({len(normal)}) with field visit history:   {n_vis} ({n_vis/len(normal)*100:.0f}%)')
print()

# Schlecht vs Normal - meter read rate
mrs['gw_norm'] = normalize_gw(mrs['gateway_id'])
mrs['read_rate'] = np.where(mrs['meters_expected'] > 0,
                             mrs['meters_read'] / mrs['meters_expected'], np.nan)

print('=== ENGINEER REVIEW vs METER READ RATE ===')
for label, gws in [('Schlecht', schlecht), ('Normal', normal)]:
    sub = mrs[mrs['gw_norm'].isin(gws)]
    if not sub.empty:
        print(f'{label}: n_rows={len(sub)}, mean_read_rate={sub["read_rate"].mean():.4f}, '
              f'median={sub["read_rate"].median():.4f}, '
              f'pct_below_90pct={(sub["read_rate"] < 0.9).mean()*100:.1f}%')
print()

# Schlecht vs Normal - telemetry health metrics
tel_health = pd.read_parquet('data/telemetry', columns=[
    'gateway_id', 'ts_utc', 'offline_duration_sec', 'disconnection_cnt',
    'reboot_cnt', 'no_conn_importance', 'reboot_importance'])
tel_health['gw_norm'] = normalize_gw(tel_health['gateway_id'])

print('=== ENGINEER REVIEW vs TELEMETRY HEALTH (mean per gw, then group mean) ===')
# Restrict to Feb 2026 (matching the review month)
tel_health['ts'] = pd.to_datetime(tel_health['ts_utc'], utc=True)
tel_feb = tel_health[(tel_health['ts'] >= '2026-02-01') & (tel_health['ts'] < '2026-03-01')]

gw_means = tel_feb.groupby('gw_norm')[['offline_duration_sec','disconnection_cnt',
                                        'reboot_cnt','no_conn_importance','reboot_importance']].mean()

for label, gws in [('Schlecht', schlecht), ('Normal', normal)]:
    sub = gw_means[gw_means.index.isin(gws)]
    if not sub.empty:
        print(f'{label} (n={len(sub)} gateways):')
        print(sub.mean().round(3).to_string())
        print()

print('DONE')
