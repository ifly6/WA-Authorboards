# Copyright (c) 2020 ifly6
import datetime
import glob
import os

import numpy as np
import pandas as pd

from src.helpers import write_file
from src.wa_parser import localised

# load our latest data
resolutions_list = glob.glob('../../db/resolutions*.csv')
df = pd.read_csv(max(resolutions_list, key=os.path.getctime), parse_dates=['Date Implemented'])

# load implementation
this_year = df[df['Date Implemented'] >= (
        localised(pd.Timestamp(datetime.datetime.now())) - pd.Timedelta(days=365)
)].copy()
this_year.to_csv('../../output/ANNUAL_resolutions.csv', index=False)


def tag(c, param):
    return f'[{param}]{c}[/{param}]'


def truncate_time(dt):
    return dt.astype(str).str.slice(stop=len('YYYY-MM-DD'))


# drop extraneous columns and column descriptions
this_year['Date Implemented'] = truncate_time(this_year['Date Implemented'])
this_year.rename(columns={'Date Implemented': 'Implemented', 'Number': '#'}, inplace=True)
this_year.drop(columns=['Votes For', 'Votes Against'], inplace=True)

# to table
strings = [tag(''.join(tag(tag(c, 'b'), 'td') for c in this_year.columns), 'tr')]  # first row is headers
for row in this_year.replace({np.nan: ''}).values:
    strings.append(
        tag(''.join(tag(c, 'td') for c in row), 'tr')
    )

annual_table = tag(''.join(strings), 'table')
print(annual_table)

write_file('../../output/ANNUAL_table.txt', annual_table)

# always use four groups...
dfs = np.array_split(this_year, 4)
for i, split in enumerate(dfs):
    l_string = tag('\n'.join(['[*]' + s for s in split['Title'].values]), 'list')
    s = f'''The GA is for resolution lovers!
    
This is Group {i + 1} for the {datetime.datetime.now().year} "Best Resolution" contest. Vote only for what you 
believe to be the best [b]two[/b] resolutions of the following in the poll above! 
    
{l_string}'''

    write_file(f'../../output/ANNUAL_post{i + 1}.txt', s)
