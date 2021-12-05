#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import glob
import os

# ---------
# load data
# ---------

# load the latest resolution version
last_resolution = sorted(
    glob.glob('../../db/resolution*.csv'), key=os.path.getmtime)[-1]
resolutions = pd.read_csv(last_resolution).rename(
    columns=lambda s: s.lower().replace(' ', '_'))

# shittily turn date implemented into date only
resolutions['date_implemented'] = pd.to_datetime(
    resolutions['date_implemented'].astype(str).str[:10])

# if it is a repeal, it is not eligible!
resolutions['_eligible'] = np.where(
    resolutions['title'].str.lower().str.contains('^repeal ', regex=True), 0, 1)

# determine whether resolutions are repealed
repeals = resolutions.loc[resolutions['category'].str.lower().eq('repeal'), [
    'sub-category']]
repeals['sub-category'] = pd.to_numeric(
    repeals['sub-category'], errors='coerce')

_res = resolutions[['number']].merge(
    repeals, how='left', left_on='number', right_on='sub-category')
_res.dropna(subset=['sub-category'], inplace=True)

# mask cross to get repeal state
resolutions['_repealed'] = np.where(
    resolutions['number'].isin(_res['number']), 1, 0)

# mark already repealed resolutions as not eligible
resolutions['_eligible'].mask(resolutions['_repealed'].eq(1), 0, inplace=True)
resolutions.at[resolutions['number'] == 1,
               '_eligible'] = 0  # mark GA 1 as ineligible

# ---------------
# calculate score
# ---------------
expiry = resolutions[resolutions['_eligible'] == 1].copy()
expiry['age'] = (pd.Timestamp('2021-08-31')
                 - expiry['date_implemented']).dt.days
expiry['pct_for'] = expiry.eval(
    'votes_for / (votes_for + votes_against)') * 100

for i in range(1, 16 + 1):
    expiry[f'score{i}'] = expiry.eval(f'age - {i} * (pct_for - 50)')
    print(f'calculated score {i}')

for i in range(1, 16 + 1):
    expiry[f'rank{i}'] = expiry[f'score{i}'].argsort()[::-1].argsort().values

expiry.sort_values(by='score7', ascending=False, inplace=True)
expiry.drop(
    columns=[
        'category',
        'sub-category',
        'author',
        'co-authors',
        'votes_for',
        'votes_against',
        'date_implemented',
        '_eligible',
        '_repealed'],
inplace=True)

# save it
expiry.to_csv('~/Desktop/ga-expiration-test.csv', index=False)

# latex
renames = {
    'number': 'GA \#',
    'title': 'Title',
    'age': 'Age (days)',
    'pct_for': '\% for',
    'score7': 'Score ($N = 7$)',
    'rank1': 'Rank 1',
    'rank3': 'Rank 3',
    'rank5': 'Rank 5',
    'rank7': 'Rank 7',
    'rank9': 'Rank 9',
}
pretty = expiry.rename(columns=renames)[renames.values()]

pretty['Age (days)'] = pretty['Age (days)'].map(lambda s: '{:,}'.format(s).replace(',', '~'))
pretty['Score ($N = 7$)'] = pretty['Score ($N = 7$)'].map(lambda s: '{:,.2f}'.format(s).replace(',', '~'))
pretty.columns = pd.MultiIndex.from_tuples(
    ('Rank' if 'Rank' in s else '', s if 'Rank' not in s else s[-1])
    for s in pretty.columns)

print(pretty.head(20).to_latex(
    float_format="%.2f", escape=False, index=False, na_rep=''
))


