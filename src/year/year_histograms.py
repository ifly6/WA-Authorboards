# Copyright (c) 2020 ifly6
# Creates chart of the number of resolutions per year. Drops incomplete years.
import glob
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.ticker import AutoMinorLocator

# load our latest data
resolutions_list = glob.glob('../../db/resolutions*.csv')
df = pd.read_csv(max(resolutions_list, key=os.path.getctime), parse_dates=['Date Implemented'])
df['Date Implemented'] = pd.to_datetime(df['Date Implemented'], utc=True)

df['year'] = df['Date Implemented'].dt.year
year_counts = df.groupby('year')['Number'].count().reset_index()
year_counts = year_counts[~year_counts['year'].isin([datetime.today().year, 2008])] # drop first year and current year
year_counts['year'] = year_counts['year'].astype(str)
print(year_counts)

year_mean = year_counts['Number'].mean()
print(f'mean resolutions per year is {year_mean}')

f, ax = plt.subplots(figsize=(8.25, 11.71))

wa_green = [i / 255 for i in (80, 116, 72, 0.9 * 255)]
hot_pink = [i / 255 for i in (231, 74, 188, 0.9 * 255)]
ax.barh(year_counts['year'], year_counts['Number'], color=hot_pink, zorder=2)

ax.invert_yaxis()
ax.xaxis.set_minor_locator(AutoMinorLocator())
ax.xaxis.grid(True, linestyle='dashed', which='major', zorder=0)
ax.xaxis.grid(True, linestyle='dotted', which='minor', zorder=0)
ax.set_title('Number of resolutions by year')
ax.annotate(
    'Data as of {}. See https://github.com/ifly6/WA-Authorboards.'.format(datetime.today().strftime('%Y-%m-%d')),
    (0, 0), (0, -20), xycoords='axes fraction', textcoords='offset points', va='top'
)

plt.axvline(x=year_mean, color='k', linestyle='--')

f.tight_layout()
f.savefig('../../output/year_counts.jpg')
print('wrote chart')
