import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import sys
sys.path.insert(0, '.')
from compare import from_county, from_precinct, compare

c_raw = pd.read_csv('2024/20240604__sd__primary__county.csv').set_index('county').sort_values(by=['county', 'office'])
p_raw = pd.read_csv('2024/20240604__sd__primary__precinct.csv')
p_raw = p_raw.set_index('county').sort_values(
    by=['county', 'office', 'district', 'candidate']
)[['office', 'district', 'candidate', 'party', 'precinct', 'votes']]

# These counties have no precinct files for 2024 primary
skip = {'Codington', 'Minnehaha', 'Pennington'}
c_names = sorted(set(c_raw.index.drop_duplicates()) - skip)
p_names = set(p_raw.index.drop_duplicates())

diffs = {}
for name in c_names:
    if name not in p_names:
        print(f'WARNING: {name} in county file but not precinct file')
        continue
    county = from_county(name, c_raw)
    precinct = from_precinct(name, p_raw)
    diff = compare(county, precinct)
    if not diff.empty:
        diffs[name] = diff

print(f'\nMissing precinct data: {sorted(skip)}\n')

if not diffs:
    print('No discrepancies found for remaining counties.')
else:
    frames = []
    for county_name, df in diffs.items():
        df2 = df.copy()
        df2.insert(0, 'county', county_name)
        frames.append(df2)
    all_diffs = pd.concat(frames, ignore_index=True)
    print(f'{len(all_diffs)} discrepant rows across {len(diffs)} counties:\n')
    print(all_diffs.to_string(index=False))
    all_diffs.to_csv('discrepancies_2024_primary.csv', index=False)
    print(f'\nSaved to discrepancies_2024_primary.csv')
