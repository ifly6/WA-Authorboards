import glob
import os
import re
import time
from datetime import datetime, timedelta
from functools import cache
from typing import List

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup

from helpers import ref, write_file

# CORE PARAMETERS
from reports.pandas_reports import df_to_bbcode

THREAD_URL = 'https://forum.nationstates.net/viewtopic.php?f=9&t=501821'  # thread to look in
BALLOT_TAG = '#2020_ga_ann_rev_1'  # starting tag for ballot
PRINT_MISSING_AUTHORS = True  # prints missing authors if True
posts_seen = [38509070]  # include posts to exclude here, only works properly if posts on first page


# HELPER FUNCTIONS
def duplicates(collection: List, excluding=None):
    if excluding is None:
        excluding = ['...']

    seen = set()
    for element in collection:
        if element in seen and element not in excluding:
            return True
        seen.add(element)
    return False


assert duplicates(['...', '...']) is False
assert duplicates([1, 1, 2]) is True


@cache  # cached to minimise IO time
def load_latest_db():
    df = pd.read_csv(max(glob.glob('../../db/resolutions*.csv'), key=os.path.getctime))
    df['Date Implemented'] = pd.to_datetime(df['Date Implemented'])
    return df


def join_author_lists_as_set(df):
    df = df.copy()
    df['Co-authors'] = df['Co-authors'].fillna('')
    joined = df[['Author', 'Co-authors']] \
        .apply(lambda r: [ref(s) for s in set(','.join(r.values).split(','))], axis=1) \
        .explode()
    joined = joined[joined != '']
    return set(joined.values)


@cache
def get_full_author_list():
    return join_author_lists_as_set(load_latest_db())


@cache
def get_latest_author_list(within_days=365 * 2):
    df = load_latest_db()
    df = df[df['Date Implemented'] > (datetime.now(pytz.utc) - timedelta(days=within_days))]
    return join_author_lists_as_set(df)


class AnnRevEntry:
    def __init__(self, voter, post_num, parsed_ballot, max_entries=10):
        self.voter_name = ref(voter)
        if not self.is_valid_voter(voter): raise RuntimeError('voter {} ineligible'.format(voter))

        self.ballot = parsed_ballot  # internally is [[1, 'title'], [2, 'title']]
        ranks, resolution_list = [], []
        for internal_list in parsed_ballot:
            ranks.append(internal_list[0])  # list of numbers as parsed_ballot
            resolution_list.append(internal_list[1])  # list of resolution titles in parsed_ballot

        if max(ranks) > max_entries: raise RuntimeError('more provided rankings than max')
        if duplicates(ranks, excluding=[]): raise RuntimeError('duplicate entry of same rank')
        if duplicates(resolution_list): raise RuntimeError('same resolution provided more than once')

        self.post_num = post_num
        print(f'validated entry {self}')

    def generate_scores(self, max_entries=10):
        """ Generates dict with entries 'title lowercase': int(score). Scores determined by Borda count. """
        scores = {}

        for rank_tuple in self.ballot:
            points = max_entries + 1 - rank_tuple[0]
            resolution = rank_tuple[1]
            scores[str(resolution).lower().strip()] = int(points)

        return scores

    @staticmethod
    def __badge_check(title_list):
        accepted = list(map(lambda s: ref(s), ['general assembly resolution author', 'Historical Resolution Author']))
        title_list = list(map(lambda s: ref(s), title_list))
        for accept in accepted:
            if any(accept in s for s in title_list):
                return True
        return False

    @staticmethod
    def is_valid_voter(voter_name):
        """ Returns true if nation is a GA resolution author or co-author or if has trophy saying it is a GA or UN
        resolution author. """
        if ref(voter_name) in get_full_author_list(): return True

        url = 'https://www.nationstates.net/nation={}'.format(voter_name.lower().replace(' ', '_'))
        title_list = [image.attrs['title'] for image in
                      BeautifulSoup(requests.get(url).text, 'lxml').select('div.trophyline span.trophyrack img')]

        time.sleep(2)  # rate limit
        return AnnRevEntry.__badge_check(title_list)

    def __str__(self):
        return f'AnnRevEntry[voter={self.voter_name}, post_num={self.post_num}]'


assert AnnRevEntry.is_valid_voter('imperium anglorum') is True
assert AnnRevEntry.is_valid_voter('araraukar') is True
assert AnnRevEntry.is_valid_voter('separatist peoples') is True
assert AnnRevEntry.is_valid_voter('knootoss') is True
assert AnnRevEntry.is_valid_voter('transilia') is False

print('starting parse')
entry_list = []
error_list = []
for i in range(10):  # 10 pages max
    print(f'starting parse for page {i + 1}')
    skip_value = i * 25
    current_url = THREAD_URL + f'&start={skip_value}'

    # check response
    response = requests.get(current_url)
    if response.status_code != 200 or \
            'Sorry but the board is temporarily unavailable, please try again in a few minutes.' in response.text:
        print('NS forum is down')
        quit(1)

    soup = BeautifulSoup(response.text, 'lxml')

    posts = soup.select('div.post')
    for post in posts:
        post_number = int(re.search(r'\d+', post.select('p.author a')[0].attrs['href']).group(0))  # get post number
        if post_number in posts_seen:  # skip post if already seen
            continue  # continue if hitting duplicate
        else:
            posts_seen.append(post_number)

        author_name = post.select('p.author a')[1].text

        post_content = post.select_one('div.content').get_text(separator='\n')
        if BALLOT_TAG in post_content:
            ballot = re.search(r'(?<=' + BALLOT_TAG + r')(.|\n)*(?=#end)', post_content)
            if ballot:
                ballot_str = ballot.group(0).strip()
                # print(ballot_str)

                ranking = []
                for ballot_line in ballot_str.splitlines():
                    parsed_line = re.search(r'\((\d+)\) ?(.*)', ballot_line)
                    ranking.append([int(parsed_line.group(1)), parsed_line.group(2)])

                try:
                    # throws error on validation fail
                    new_entry = AnnRevEntry(author_name, post_number, ranking)

                    # if attempting to vote twice, skip
                    if author_name in set(entry.voter_name for entry in entry_list):
                        error_list.append(
                            f'voter {author_name} attempted to vote twice! post id {post_number}. skipped')

                    # throw error if saving duplicate
                    if post_number in set(entry.post_num for entry in entry_list):
                        raise RuntimeError('duplicate post number for entry:' + str(new_entry))  # shouldn't happen

                    entry_list.append(new_entry)

                except RuntimeError as e:
                    # log validation error
                    error_list.append(f'entry for {author_name} at post {post_number} failed validation: {e}')

            else:
                error_list.append(f'post by {author_name} has ballot tag but no #end ?')

    # break out of loop if hitting duplicate
    page_postnum = int(re.search(r'\d+', soup.select('p.author a')[0].attrs['href']).group(0))  # get post number
    if page_postnum in posts_seen and i != 0:
        print(f'seen duplicate post number {page_postnum}; breaking loop')
        break

    if not (i == 0 or i == 9):
        time.sleep(2)  # sleep 5 seconds __between__ pages, exclude first and last

print('loaded web ballot data')

resolutions = pd.read_csv('../../output/ANNUAL_resolutions.csv')
resolutions['Implemented'] = pd.to_datetime(resolutions['Implemented'], utc=True)
resolutions['Score'] = 0
resolutions['_lowercase_titles'] = resolutions['Title'].str.lower().str.strip()
print('loaded resolutions data')

# check for puppets
aliases = pd.read_csv('../../db/aliases.csv')
aliases['_joined'] = aliases.apply(lambda r: [ref(s) for s in set(','.join(r.values).split(','))], axis=1)
for alias_list in aliases['_joined'].values:
    voters = [ref(e.voter_name) for e in entry_list]
    results_dict = dict([(a, a in voters) for a in alias_list])
    if sum(results_dict.values()) > 1:
        duplicate_names = [k for k, v in results_dict.items() if v]
        print('aliases ' + str(duplicate_names) + ' appear more than once!')
        print('removing later vote')

        matching_entries = sorted([e for e in entry_list if e.voter_name in duplicate_names],
                                  key=lambda the_ballot: the_ballot.post_num, reverse=False)
        r_entries = matching_entries[1:]  # everything after last

        for r_entry in r_entries:
            entry_list.remove(r_entry)

        error_list.append(f'removed entries {r_entries} because entries attempted to vote twice')

# tally scores
for entry in entry_list:
    entry: AnnRevEntry

    score_dict = entry.generate_scores()
    for k, v in score_dict.items():
        try:
            old_score = resolutions.loc[resolutions['_lowercase_titles'] == k, 'Score'].values[0]  # unwrap series
            new_score = old_score + v
            resolutions.loc[resolutions['_lowercase_titles'] == k, 'Score'] = new_score
            print(f'from {entry} modified score for {k} from {old_score} to {new_score}')
        except IndexError:
            error_list.append(f'skipped non-existent resolution \'{k}\' in entry {entry}')

# remove extraneous columns
resolutions.sort_values(by=['Score', 'Pct For'], ascending=False, inplace=True)
resolutions.drop(columns=[s for s in resolutions.columns if s.startswith('_')], inplace=True)

# print full results
resolutions.to_csv('../../output/ANNUAL_resolutions_tally.csv', index=False)

# print summary results for forum
formatted_resolutions = resolutions.fillna('')\
    .drop(columns=['Pct For', 'Votes For', 'Votes Against', 'Implemented', 'Author', 'Co-authors']) \
    .query('Score != 0')
promoted_resolutions = formatted_resolutions.head(10)
write_file('../../output/ANNUAL_resolutions_tally_table.txt', df_to_bbcode(formatted_resolutions))
write_file('../../output/ANNUAL_resolutions_tally_table_top10.txt', df_to_bbcode(promoted_resolutions))

# tell user
print('complete')

# if we have errors, print them
if len(error_list) != 0:
    print('got errors: ')
    print('\n'.join('\t' + str(s) for s in error_list))

else:
    print('no errors')

# print out the authors from the last two years who have not yet voted
if PRINT_MISSING_AUTHORS:
    latest_authors = get_latest_author_list()
    entry_authors = [e.voter_name for e in entry_list]
    missing_authors = [s for s in latest_authors if ref(s) not in entry_authors]
    if len(missing_authors) > 0:
        print('the following authors have not voted')
        for s in missing_authors:
            print(f'\t {s}')
