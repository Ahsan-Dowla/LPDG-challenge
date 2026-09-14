import pandas as pd, numpy as np

# ---- meter_read_success ----
mrs = pd.read_csv('data/meter_read_success.csv')
print('MRS ROWS:', len(mrs), '  COLS:', mrs.shape[1])
print('COLUMNS:', list(mrs.columns))
print()

n = mrs.isnull().sum()
ndf = pd.DataFrame({'null_count': n, 'null_pct': (n/len(mrs)*100).round(2)}).query('null_count>0')
print('NULLS:'); print(ndf.to_string()); print()

if 'week_start' in mrs.columns:
    mrs['week_start'] = pd.to_datetime(mrs['week_start'])
    print('WEEK range:', mrs['week_start'].min().date(), '->', mrs['week_start'].max().date())
    print('UNIQUE weeks:', mrs['week_start'].nunique())

print('UNIQUE gateways:', mrs['gateway_id'].nunique() if 'gateway_id' in mrs.columns else 'N/A')
print()

for col in ['meters_expected', 'meters_read']:
    if col in mrs.columns:
        print(f'{col}:'); print(mrs[col].describe().round(2).to_string()); print()

if 'meters_expected' in mrs.columns and 'meters_read' in mrs.columns:
    mrs['read_rate'] = np.where(mrs['meters_expected'] > 0,
                                mrs['meters_read'] / mrs['meters_expected'], np.nan)
    print('READ RATE stats:'); print(mrs['read_rate'].describe().round(4).to_string())
    print('  read_rate < 0.9:', (mrs['read_rate'] < 0.9).sum())
    print('  read_rate < 0.5:', (mrs['read_rate'] < 0.5).sum())
    print('  read_rate > 1.0 (impossible):', (mrs['read_rate'] > 1.0).sum())
    print('  denominator zero:', (mrs['meters_expected'] == 0).sum())
    print()

# Missing gateway-week combos
if 'gateway_id' in mrs.columns and 'week_start' in mrs.columns:
    all_weeks = mrs['week_start'].unique()
    all_gws   = mrs['gateway_id'].unique()
    full_idx  = pd.MultiIndex.from_product([all_gws, all_weeks],
                                            names=['gateway_id','week_start'])
    actual_idx = pd.MultiIndex.from_frame(mrs[['gateway_id','week_start']])
    n_missing  = len(full_idx.difference(actual_idx))
    print(f'MISSING gateway-week combos: {n_missing} / {len(full_idx)} ({n_missing/len(full_idx)*100:.1f}%)')

    # Per-gateway coverage
    gw_counts = mrs.groupby('gateway_id')['week_start'].count()
    print('Per-gateway week count stats:'); print(gw_counts.describe().to_string())
    low_cov = gw_counts[gw_counts < gw_counts.max() * 0.5]
    print(f'Gateways with <50% week coverage: {len(low_cov)}')

print('DONE')
