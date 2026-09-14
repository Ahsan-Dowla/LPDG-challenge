import pandas as pd, numpy as np

# ---- field_visits ----
fv = pd.read_csv('data/field_visits.csv')
print('FV ROWS:', len(fv), '  COLS:', fv.shape[1])
print('COLUMNS:', list(fv.columns))
print()

n = fv.isnull().sum()
ndf = pd.DataFrame({'null_count': n, 'null_pct': (n/len(fv)*100).round(2)}).query('null_count>0')
print('NULLS:'); print(ndf.to_string() if not ndf.empty else 'None'); print()

print('UNIQUE gateways with visits:', fv['gateway_id'].nunique() if 'gateway_id' in fv.columns else 'N/A')

if 'gateway_id' in fv.columns:
    vc = fv['gateway_id'].value_counts()
    print('Visits per gateway (describe):'); print(vc.describe().to_string())
    print('Top-10 frequently visited:'); print(vc.head(10).to_string())
    print('Gateways visited once:', (vc == 1).sum())
    print()

# Date column
for dc in fv.columns:
    if 'date' in dc.lower() or 'ts' in dc.lower() or 'time' in dc.lower():
        try:
            fv[dc] = pd.to_datetime(fv[dc])
            print(f'{dc} range: {fv[dc].min().date()} -> {fv[dc].max().date()}')
        except Exception:
            pass

print()
for col in fv.select_dtypes(include='object').columns:
    if col == 'gateway_id':
        continue
    vc = fv[col].value_counts(dropna=False)
    print(f'{col} ({len(vc)} unique vals):')
    print(vc.head(10).to_string())
    print()

for col in fv.select_dtypes(include='number').columns:
    print(f'{col}:'); print(fv[col].describe().round(3).to_string()); print()

print('DONE')
