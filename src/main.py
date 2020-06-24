import glob
import os
import pandas as pd

from src import wa_parser
from src.load_db import Database
from src.reports import (generate_author_index, generate_author_table,
                         generate_known_aliases, OrderType)


def write_file(path, s):
    if not path.endswith('.txt'):
        path = path + '.txt'

    with open(path, 'w') as f:
        f.write(s)


print('starting')
updating_database = True

if updating_database:
    newdf_path = '../db/resolutions_{}.csv'.format(pd.Timestamp.now().strftime('%Y-%m-%d'))
    df = wa_parser.parse()
    df.to_csv(newdf_path, index=False)

print('parsing database')

resolution_csvs = glob.glob('../db/resolutions*.csv')
latest = max(resolution_csvs, key=os.path.getctime)

# db = Database.create('../db/resolutions.csv', '../db/aliases.csv')
db = Database.create(latest, '../db/aliases.csv')

print('saving tables')

os.makedirs('../output', exist_ok=True)

write_file('../output/author_index', generate_author_index(db))
write_file('../output/table_AUTHOR', generate_author_table(db, OrderType.AUTHOR))
write_file('../output/table_LEADERBOARDS', generate_author_table(db, OrderType.TOTAL))
write_file('../output/table_ACTIVE_TOTAL', generate_author_table(db, OrderType.ACTIVE_TOTAL))
write_file('../output/table_NON_REPEALS', generate_author_table(db, OrderType.ACTIVE_NON_REPEALS_TOTAL))
write_file('../output/table_REPEALS', generate_author_table(db, OrderType.ACTIVE_REPEALS_TOTAL))
write_file('../output/table_REPEALED', generate_author_table(db, OrderType.REPEALED_TOTAL))
write_file('../output/author_aliases', generate_known_aliases(db))
