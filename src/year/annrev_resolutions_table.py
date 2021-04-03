# Copyright (c) 2020 ifly6
# Creates annual review resolution summary table
import glob
import os

import numpy as np
import pandas as pd

from src.helpers import write_file

SMALL_TABLE = False

# load our latest data
resolutions_list = glob.glob('../../db/resolutions*.csv')
df = pd.read_csv(max(resolutions_list, key=os.path.getctime), parse_dates=['Date Implemented'])
df['Date Implemented'] = pd.to_datetime(df['Date Implemented'], utc=True)

# load implementation
this_year = df[df['Date Implemented'].dt.year == 2020].copy()
this_year.to_csv('../../output/ANNUAL_resolutions.csv', index=False)


def tag(c, param):
    return f'[{param}]{c}[/{param}]'


def truncate_time(dt):
    return dt.astype(str).str.slice(stop=len('YYYY-MM-DD'))


# drop extraneous columns and column descriptions
this_year['Date Implemented'] = truncate_time(this_year['Date Implemented'])
this_year.rename(columns={'Date Implemented': 'Implemented', 'Number': '#'}, inplace=True)

this_year['Pct For'] = (this_year['Votes For'] * 100 / (this_year['Votes For'] + this_year['Votes Against'])) \
    .apply(lambda s: '{:,.2f}%'.format(s))

if SMALL_TABLE:
    this_year.drop(columns=['Votes For', 'Votes Against', 'Author', 'Co-authors'], inplace=True)  # remove for full table
    this_year.drop(columns=['Pct For'], inplace=True)

this_year['Sub-category'] = this_year.apply(
    lambda r: 'GA ' + r['Sub-category'] if r['Category'] == 'Repeal' else r['Sub-category'],
    axis=1)

# to table
strings = [tag(''.join(tag(tag(c, 'b'), 'td') for c in this_year.columns), 'tr')]  # first row is headers
for row in this_year.replace({np.nan: ''}).values:
    strings.append(
        tag(''.join(tag(c, 'td') for c in row), 'tr')
    )

annual_table = tag(''.join(strings), 'table')
print(annual_table)

write_file('../../output/ANNUAL_table.txt', annual_table)
