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
from reports.pandas_reports import df_to_bbcode

# CORE PARAMETERS
THREAD_URL = ... # thread to look in
BALLOT_TAG = '#2021_ga_ann_rev_1'  # starting tag for ballot
PRINT_MISSING_AUTHORS = True  # prints missing authors if True
COUNT_TYPE = 'harmonic'
posts_seen = [38509070, 38574108]  # include posts to exclude here, only works properly if posts on first page


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
    def __init__(self, voter, post_num, parsed_ballot, max_entries=10, require_all_ranks=False):
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
        if set(ranks) != set(range(1, max_entries + 1)) and require_all_ranks:
            raise RuntimeError('incomplete, rankings not fully expressed')

        self.post_num = post_num
        print(f'validated entry {self}')

    def generate_scores(self, max_entries=10, count_type=COUNT_TYPE):
        """ Generates dict with entries 'title lowercase': int(score). Scoring determined by count_type.

        Borda count assigns a rank and then all later ranks are given a score one less than the previous rank: thus,
        1 -> 10, 2 -> 9, 3 -> 8, etc.

        Harmonic yields scores of 1000 / rank, so rank 1 -> 1000, 2 -> 500, 3 -> 333, etc. This weights more heavily
        towards top preferences. Geometric even more heavily weights top preferences: for 1, it follows
        1000 / 2^(rank - 1), so 1 -> 1000, 2 -> 500, 3 -> 250, etc."""
        scores = {}
        for rank, title in self.ballot:
            if count_type == 'borda' or count_type == 'arithmetic':
                points = max_entries + 1 - rank
            elif count_type == 'harmonic':
                points = 1000 / rank  # need more precision, 10/9 approx == 10/10 after rounding, use 1000
            elif count_type == 'geometric':
                points = 1000 / (2 ** (rank - 1))  # need even more precision, 1000 / 2^10 = 0.97, approx 1.
            else:
                raise TypeError(f'provided count type "{count_type}" is not supported')

            resolution = title
            scores[str(resolution).lower().strip()] = round(points)
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


assert AnnRevEntry.is_valid_voter('imperium anglorum') is True  # has badges
assert AnnRevEntry.is_valid_voter('araraukar') is True  # has co-authors
assert AnnRevEntry.is_valid_voter('separatist peoples') is True  # is gensec, isn't WA?
assert AnnRevEntry.is_valid_voter('knootoss') is True  # is older author
assert AnnRevEntry.is_valid_voter('transilia') is False  # is not a WA author

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

    # break out of loop if hitting duplicate
    # break section must be before main post parsing
    page_postnum = int(re.search(r'\d+', soup.select('p.author a')[0].attrs['href']).group(0))  # get post number
    if page_postnum in posts_seen and i != 0:
        print(f'seen duplicate post number {page_postnum}; breaking loop')
        break

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
    score_dict = entry.generate_scores()
    for k, v in score_dict.items():
        completed = False

        # correct possible spelling localisation errors, one of the fixes works, then it is kept and breaks loop,
        # otherwise it continues attempting error fixes until there are no more, when it will print that an entry was
        # skipped due to non-completion
        for error, correction in [('', ''),
                                  (r'zation(?=\s|$)', 'sation'),  # civilization -> civilisation
                                  (r'sation(?=\s|$)', 'zation'),
                                  (r'or(?=\s|$)', 'our'),  # honor -> honour
                                  (r'our(?=\s|$)', 'or'),
                                  (r'(?<=\s|^)arti', 'arte'),  # artifact -> artefact
                                  (r'(?<=\s|^)arte', 'arti'), ]:
            try:
                new_key = re.sub(error, correction, k)
                old_score = resolutions.loc[resolutions['_lowercase_titles'] == new_key, 'Score'].values[0]
                new_score = old_score + v
                resolutions.loc[resolutions['_lowercase_titles'] == new_key, 'Score'] = new_score
                print(f'from {entry} modified score for {k} from {old_score} to {new_score}')

                # mark complete
                completed = True
                break

            except IndexError:
                pass

        if not completed:
            error_list.append(f'skipped non-existent resolution \'{k}\' in entry {entry}')

# remove extraneous columns
resolutions.sort_values(by=['Score', 'Pct For'], ascending=False, inplace=True)
resolutions.drop(columns=[s for s in resolutions.columns if s.startswith('_')], inplace=True)

# print full results
resolutions.to_csv('../../output/ANNUAL_resolutions_tally.csv', index=False)

# print summary results for forum
formatted_resolutions = resolutions.fillna('') \
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
