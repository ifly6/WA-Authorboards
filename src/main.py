# Copyright (c) 2017 Auralia
# Modifications, copyright (c) 2020 ifly6
import glob
import os
from datetime import datetime
from os.path import exists

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

from src import wa_parser
from src.helpers import write_file
from src.reports.bbcode_reports import *
from src.reports.pandas_reports import create_leaderboards, create_aliases

print('starting')
updating_database = True
writing_files = True

# ensure folders for relevant directories exist
for p in ['../output', '../md_output', '../db', '../db/cache']:
    os.makedirs(p, exist_ok=True)

for p in ['../db/aliases.csv', '../db/names.txt']:
    if not exists(p):
        raise FileNotFoundError(f'file {p} must exist')

if updating_database:
    print('updating database')
    df_path = '../db/resolutions_{}.csv'.format(pd.Timestamp.now().strftime('%Y-%m-%d'))
    df = wa_parser.parse()
    df.to_csv(df_path, index=False)

# parse database
print('parsing database')
db = Database.create(max(glob.glob('../db/resolutions*.csv'), key=os.path.getctime), '../db/aliases.csv')
# > uncomment below to generate for explicit path
# db = Database.create('../db/resolutions.csv', '../db/aliases.csv')

# create table
print('creating markdown table')
s = create_leaderboards(db, how='markdown')
write_file('../md_output/leaderboard.md', s, print_input=True)

print('creating markdown table no puppets')
s = create_leaderboards(db, how='markdown', keep_puppets=False)
write_file('../md_output/leaderboard-no-puppets.md', s, print_input=True)

# create alias table
print('creating alias table')
s = create_aliases()
write_file('../md_output/aliases.md', s, print_input=True)

# create chart
print('creating chart')
ranks = create_leaderboards(db, how='pandas', keep_puppets=False)
ranks['Name'] = ranks['Name'].str.replace(r'\[PLAYER\]', '', regex=True).str.strip()  # de-dup from players
ranks.drop_duplicates(subset='Name', keep='first', inplace=True)
ranks = ranks[ranks['Rank'] <= 30]

f, ax = plt.subplots(figsize=(8.25, 11.71))
ax.barh(ranks['Name'], ranks['Total'], color=sns.color_palette('muted'), zorder=2)
ax.set_ylim([-1, ranks['Name'].size])
ax.invert_yaxis()
ax.xaxis.set_minor_locator(AutoMinorLocator())
ax.xaxis.grid(True, linestyle='dashed', which='major', zorder=0)
ax.xaxis.grid(True, linestyle='dotted', which='minor', zorder=0)
ax.set_title('Players with most WA resolutions')
ax.annotate(
    'Data as of {}. See https://github.com/ifly6/WA-Authorboards.'.format(datetime.today().strftime('%Y-%m-%d')),
    (0, 0), (0, -20), xycoords='axes fraction', textcoords='offset points', va='top'
)

f.tight_layout()
f.savefig('../md_output/leaderboard_top30.pdf')
f.savefig('../md_output/leaderboard_top30.jpg')
print('wrote chart')

# write old bbCode files
if writing_files:
    print('saving tables')
    write_file('../output/author_index', generate_author_index(db))
    write_file('../output/table_AUTHOR', generate_author_table(db, OrderType.AUTHOR))
    write_file('../output/table_LEADERBOARDS', generate_author_table(db, OrderType.TOTAL))
    write_file('../output/table_ACTIVE_TOTAL', generate_author_table(db, OrderType.ACTIVE_TOTAL))
    write_file('../output/table_NON_REPEALS', generate_author_table(db, OrderType.ACTIVE_NON_REPEALS_TOTAL))
    write_file('../output/table_REPEALS', generate_author_table(db, OrderType.ACTIVE_REPEALS_TOTAL))
    write_file('../output/table_REPEALED', generate_author_table(db, OrderType.REPEALED_TOTAL))
    write_file('../output/author_aliases', generate_known_aliases(db))
