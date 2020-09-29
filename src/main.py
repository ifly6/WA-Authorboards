import glob
import os
from datetime import datetime

import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns

from src import wa_parser
from src.helpers import write_file
from src.reports.bbcode_reports import *
from src.reports.pandas_reports import create_leaderboards

print('starting')
updating_database = False
writing_files = False

# ensure folders for relevant directories exist
for p in ['../output', '../db']:
    os.makedirs(p, exist_ok=True)

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
s = create_leaderboards(db, format='markdown')
write_file('../md_output/leaderboard.md', s)
print(s)

# create chart
print('creating chart')
ranks = create_leaderboards(db, format='pandas', keep_puppets=False)
ranks['Name'] = ranks['Name'].str.replace(r'\[PLAYER\]', '').str.strip()  # de-dup from players
ranks.drop_duplicates(subset='Name', keep='first', inplace=True)
ranks = ranks.head(30)

f, ax = plt.subplots(figsize=(8.25, 11.71))
ax.barh(ranks['Name'], ranks['Total'], color=sns.color_palette('muted'))
ax.set_ylim([-1, ranks['Name'].size])
ax.invert_yaxis()
ax.xaxis.grid(True, linestyle='--')
ax.set_title('Players with most WA resolutions')
ax.annotate('As of {}'.format(datetime.today().strftime('%Y-%m-%d')), (0, 0), (0, -20),
            xycoords='axes fraction', textcoords='offset points', va='top')

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
