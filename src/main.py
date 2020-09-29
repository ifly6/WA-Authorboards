import glob
import os

import pandas as pd

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
    df_path = '../db/resolutions_{}.csv'.format(pd.Timestamp.now().strftime('%Y-%m-%d'))
    df = wa_parser.parse()
    df.to_csv(df_path, index=False)

print('parsing database')

# > uncomment below to generate for explicit path
# db = Database.create('../db/resolutions.csv', '../db/aliases.csv')

resolutions_list = glob.glob('../db/resolutions*.csv')
db = Database.create(max(resolutions_list, key=os.path.getctime), '../db/aliases.csv')

s = create_leaderboards(db, format='markdown')
write_file('../md_output/leaderboard.md', s)
print(s)

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
