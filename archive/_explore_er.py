import pandas as pd, numpy as np

# ---- engineer_review ----
er = pd.read_excel('data/engineer_review_2026-02.xlsx')
print('ER ROWS:', len(er), '  COLS:', er.shape[1])
print('COLUMNS:', list(er.columns))
print()

n = er.isnull().sum()
ndf = pd.DataFrame({'null_count': n, 'null_pct': (n/len(er)*100).round(2)}).query('null_count>0')
print('NULLS:'); print(ndf.to_string() if not ndf.empty else 'None'); print()

print('UNIQUE gateways:', er['gateway_id'].nunique() if 'gateway_id' in er.columns else 'N/A')

for col in er.select_dtypes(include='object').columns:
    vc = er[col].value_counts(dropna=False)
    print(f'{col} ({len(vc)} unique):')
    print(vc.to_string())
    print()

for col in er.select_dtypes(include='number').columns:
    print(f'{col}:'); print(er[col].describe().to_string()); print()

print('DONE')
