import pandas as pd, numpy as np

# Gateway master
gm = None
for enc in ['utf-8', 'cp1252', 'latin-1']:
    try:
        gm = pd.read_csv('data/gateway_master.csv', encoding=enc)
        print(f'ENCODING: {enc}')
        break
    except UnicodeDecodeError:
        continue

print('ROWS:', len(gm), '  COLS:', gm.shape[1])
print('COLUMNS:', list(gm.columns))
print()

n = gm.isnull().sum()
p = (n/len(gm)*100).round(2)
ndf = pd.DataFrame({'null_count': n, 'null_pct': p}).query('null_count>0')
print('NULLS:')
print(ndf.to_string())
print()

print('DUPE gateway_id:', gm.duplicated(subset=['gateway_id']).sum() if 'gateway_id' in gm.columns else 'N/A')
print('UNIQUE gateways:', gm['gateway_id'].nunique() if 'gateway_id' in gm.columns else 'N/A')
print()

for col in gm.select_dtypes(include='object').columns:
    if col == 'gateway_id':
        continue
    vc = gm[col].value_counts(dropna=False)
    print(f'{col}:')
    print(vc.head(10).to_string())
    print()

for col in gm.select_dtypes(include='number').columns:
    print(f'{col}:')
    print(gm[col].describe().round(3).to_string())
    zeros = (gm[col] == 0).sum()
    negs  = (gm[col] < 0).sum()
    print(f'  zeros={zeros}  negatives={negs}')
    print()

print('DONE')
