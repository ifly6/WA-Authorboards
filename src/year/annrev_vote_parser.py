import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

base_url = 'https://forum.nationstates.net/viewtopic.php?f=9&t=501821'
ballot_tag = '#2020_ga_ann_rev_1'
posts_seen = [38509070]


def ref(s: str):
    return s.strip().lower().replace(' ', '_')


class AnnRevEntry:
    def __init__(self, voter, post_num, ranking, max_entries=10):
        rank_list = [i for i, _ in ranking]  # list of numbers as ranking
        resolution_list = [s for _, s in ranking]  # list of numbers as ranking
        if max([i for i, _ in ranking]) > max_entries: raise RuntimeError('more provided rankings than max')
        if len(rank_list) != len(set(rank_list)): raise RuntimeError('duplicate entry of same rank')
        if len(resolution_list) != len(set(resolution_list)): raise RuntimeError('resolution provided more than once')

        self.voter_name = ref(voter)
        self.post_num = post_num
        self.ranks = ranking  # internally is [[1, 'title'], [2, 'title']]

    def generate_scores(self, max_entries=10):
        """ Generates dict with entries 'title_lowercase': int(score)."""
        scores = {}

        for rank_tuple in self.ranks:
            points = max_entries + 1 - rank_tuple[0]
            resolution = rank_tuple[1]
            scores[str(resolution).lower()] = points

        return scores

    def is_valid_voter(self):
        """ Returns true if nation has trophy saying it is a GA resolution author. """
        ref_name = self.voter_name.lower().replace(' ', '_')
        url = f'https://www.nationstates.net/nation={ref_name}'
        soup = BeautifulSoup(requests.get(url).text, 'lxml')
        return any('general assembly resolution author' in i.attrs['title'].lower() for i in
                   soup.select('div.trophyline span.trophyrack img'))

    def __str__(self):
        return f'AnnRevEntry[voter={self.voter_name}, post_num={self.post_num}]'


entry_list = []
error_list = []
for i in range(10):  # 10 pages max
    skip_value = i * 25
    current_url = base_url + f'&start={skip_value}'
    soup = BeautifulSoup(requests.get(current_url).text, 'lxml')

    posts = soup.select('div.post')
    for post in posts:
        post_number = int(re.search(r'\d+', post.select('p.author a')[0].attrs['href']).group(0))  # get post number
        if post_number in posts_seen:  # skip post if already seen
            continue  # continue if hitting duplicate
        else:
            posts_seen.append(post_number)

        author_name = post.select('p.author a')[1].text

        post_content = post.select_one('div.content').get_text(separator='\n')
        if ballot_tag in post_content:
            ballot = re.search(r'(?<=' + ballot_tag + r')(.|\n)*(?=#end)', post_content)
            if ballot:
                ballot_str = ballot.group(0).strip()
                # print(ballot_str)

                ranking = []
                for ballot_line in ballot_str.splitlines():
                    parsed_line = re.search(r'\((\d+)\) ?(.*)', ballot_line)
                    ranking.append([int(parsed_line.group(1)), parsed_line.group(2)])

                try:
                    # throw error if saving duplicate
                    new_entry = AnnRevEntry(author_name, post_number, ranking)

                    if author_name in set(entry.voter_name for entry in entry_list):
                        error_list.append(
                            f'voter {author_name} attempted to vote twice at post id {post_number}. skipped!')

                    if post_number in set(entry.post_num for entry in entry_list):
                        raise RuntimeError('duplicate post number for entry:' + str(new_entry))

                    entry_list.append(new_entry)

                except RuntimeError as e:
                    error_list.append(f'error! could not create entry for {author_name} at post {post_number}! {e}')

            else:
                error_list.append(f'error! post by {author_name} has ballot tag but no #end ?')

    # break out of loop if hitting duplicate
    page_postnum = int(re.search(r'\d+', soup.select('p.author a')[0].attrs['href']).group(0))  # get post number
    if page_postnum in posts_seen:
        break

    time.sleep(2)  # sleep 5 seconds between pages

print('loaded web ballot data')

resolutions = pd.read_csv('../../output/ANNUAL_resolutions.csv')
resolutions['Date Implemented'] = pd.to_datetime(resolutions['Date Implemented'], utc=True)
resolutions['Score'] = 0
resolutions['_lowercase_titles'] = resolutions['Title'].str.lower()
print('loaded resolutions data')

# check for validity
for entry in list(entry_list):  # iterate over copy of list
    valid = entry.is_valid_voter()
    print(f'entry {entry} is ' + ('' if valid else 'not ') + 'a GA resolution author')
    if not valid:
        entry_list.remove(entry)

    time.sleep(2)

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
                                  key=lambda i: i.post_num, reverse=False)
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
            old_score = resolutions.loc[resolutions['_lowercase_titles'] == k, 'Score'].values[0]  # unwrap from series
            new_score = old_score + v
            resolutions.loc[resolutions['_lowercase_titles'] == k, 'Score'] = new_score
            print(f'from entry {entry} modified score for {k} from {old_score} to {new_score}')
        except IndexError:
            error_list.append(f'skipped non-existent resolution \'{k}\' in entry {entry}')

# remove extraneous columns
resolutions.sort_values(by='Score', ascending=False, inplace=True)
resolutions.drop(columns=[s for s in resolutions.columns if s.startswith('_')], inplace=True)

# print
resolutions.to_csv('../../output/ANNUAL_resolutions_tally.csv', index=False)

# tell user
print('complete')
print('got errors: ' + str(error_list))
