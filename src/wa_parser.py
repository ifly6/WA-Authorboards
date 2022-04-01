# Copyright (c) 2020 ifly6
import html
import io
import re
from datetime import datetime
from functools import cache
from typing import Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree
from pytz import timezone
from ratelimit import limits, sleep_and_retry

from helpers import ref
from src import wa_cacher

""" Imperium Anglorum:

This is adapted from proprietary InfoEurope code which in part does most of this already. Eg the proposal portions 
which translate, the locality adjustments, API reading, etc. There is also code in beta (not-in-production)
which would have done this entirely, but I never got around to developing the VIEWS for that portion of the website.

It seems much easier just to commit something like this given that all the code is already present.

See ifly6.no-ip.org for more information. """

_headers = {
    'User-Agent': 'WA parser (Auralia; Imperium Anglorum)'
}


class ApiError(Exception):
    pass


@sleep_and_retry
@limits(calls=25, period=30)  # 50 calls every 30 seconds they say but somehow this is fake news
def call_api(url) -> str:
    response = requests.get(url, headers=_headers)
    if response.status_code != 200:
        raise ApiError('{} error at api url: {}'.format(response.status_code, str(url)))
    return response.text


def clean_chamber_input(chamber):
    """ Turns ambiguous chamber information into tuple (int, str) with chamber id and chamber name """
    if type(chamber) == str:
        if chamber == '1':
            chamber = 1
        elif chamber == '2':
            chamber = 2
        elif chamber == 'GA':
            chamber = 1
        elif chamber == 'SC':
            chamber = 2

    chamber_name = 'GA' if chamber == 1 else \
        'SC' if chamber == 2 else ''
    return chamber, chamber_name


def localised(dt: 'datetime', tz='US/Eastern'):
    return timezone(tz).localize(dt)


@cache
def _category_map():
    d = {'Advancement of Industry': 'Environmental Deregulation',
         'Civil Rights': 'Mild',
         'Human Rights': 'Mild',
         'Education and Creativity': 'Artistic',
         'Environmental': 'Automotive',
         'Free Trade': 'Mild',
         'Furtherment of Democracy': 'Mild',
         'Global Disarmament': 'Mild',
         'Health': 'Healthcare',
         'International Security': 'Mild',
         'Moral Decency': 'Mild',
         'Political Stability': 'Mild',
         'Regulation': 'Consumer Protection',
         'Gun Control': 'Tighten',
         'Social Justice': 'Mild'}
    return {ref(k): v for k, v in d.items()}  # force ref name for matching
    # nb that this is identical to dict( ( ref(k), v ) for k, v in d.items() )


def _translate_category(category: str, s: str) -> Tuple[bool, str]:
    if ref(category) in _category_map() and s == '0':
        return True, _category_map()[ref(category)]  # yield correct name from ref name of category

    # if it isn't 0, then it doesn't apply, return given
    # if not in the list, return given
    return False, s


def capitalise(s):
    s = s.replace('_', ' ').strip()

    # exceptions
    capitalisation_exceptions = wa_cacher.load_capitalisation_exceptions()
    for i in capitalisation_exceptions:
        if s.strip().lower() == i.strip().lower():
            return i  # replace with manual correction

    # only capitalise words longer than 2 letters ('new') and always capitalise first
    # unless the word is in given list
    # > fanboys & the
    s = " ".join(
        w.capitalize()
        if (len(w) > 2 and w not in ['for', 'and', 'nor', 'but', 'yet', 'the']) or (i == 0)
        else w
        for i, w in enumerate(s.split())
    ).strip()  # avoid apostrophe capitalisations

    # but capitalise st -> St
    for exception in ['St']:
        s = ' '.join((exception if w.lower() == exception.lower() else w)
                     for w in s.split())

    # for split in ['-']:
    #     # as first should always be capitalised, not checking doesn't matter
    #     s = split.join(w[:1].upper() + w[1:] for i, w in enumerate(s.split(split)))  # capitalise first letter only
    # "Christian DeMocrats"
    # python str.capitalize forces all other chars to lower
    # don't use str.capitalize above

    for numeral in ['ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']:
        s = re.sub(r'(?<=\s){}$'.format(numeral), numeral.upper(), s)  # matches only trailing numerals

    # people used to use WA missions; capitalise these, they are separate words
    s = re.sub(r'(?<=\s)(Wa|wa|wA)(?=\s)', 'WA', s)  # if between two spaces
    s = re.sub(r'^(Wa|wa|wA)(?=\s)', 'WA', s)  # if at start (eg WA Mission of NERV-UN)

    return s


def _get_council(i):
    if i == 'GA' or i == 1: return 'GA'
    if i == 'SC' or i == 2: return 'SC'
    if i == 'UN' or i == 0: return 'UN'
    raise ValueError(f'provided council code {i} is invalid')


class WaPassedResolution:

    def __init__(self, **kwargs):
        # core vote information
        self.resolution_num = None
        self.title = None
        self.implementation = None

        # category and strength
        self.chamber = None
        self.category = None
        self.strength = None

        # handle repeals
        self.is_repealed = None
        self.repealed_by = None
        self.is_repeal = None
        self.repeals = None

        # text
        self.text = None

        # ancillary information
        self.author = None
        self.coauthor0 = None
        self.coauthor1 = None
        self.coauthor2 = None

        self.votes_for = None
        self.votes_against = None

        self.council = None

        self.__dict__.update(kwargs)  # django does this automatically, i'm not updating it; lazy

    @staticmethod
    def parse_ga(res_num, council=1):

        from src.wa_cacher import Cacher
        try:
            cacher = Cacher.load()
        except FileNotFoundError:
            cacher = Cacher()  # init new

        api_url = 'https://www.nationstates.net/cgi-bin/api.cgi?wa={}&id={}&q=resolution'.format(council, res_num)
        in_cacher = cacher.contains(api_url)
        if not in_cacher:
            this_response = call_api(api_url)
            cacher.update(api_url, this_response)
        else:
            this_response = cacher.get(api_url)

        xml = etree.parse(io.StringIO(this_response))
        if not xml.xpath('/WA/RESOLUTION/NAME'):
            raise ValueError(f'resolution number {res_num} is invalid; no such resolution exists')

        resolution_is_repealed = xml.xpath('/WA/RESOLUTION/REPEALED_BY') != []
        resolution_is_a_repeal = xml.xpath('/WA/RESOLUTION/REPEALS_COUNCILID') != []

        resolution_text = html.unescape(xml.xpath('/WA/RESOLUTION/DESC')[0].text)

        resolution_author = xml.xpath('/WA/RESOLUTION/PROPOSED_BY')[0].text
        print(resolution_author)
        print(type(resolution_author))
        if resolution_author is None or str(resolution_author).strip() == '':
            raise RuntimeError('resolution author is empty')

        author = capitalise(resolution_author)

        resolution = WaPassedResolution(
            council=_get_council(council),
            resolution_num=res_num,
            title=xml.xpath('/WA/RESOLUTION/NAME')[0].text,
            implementation=localised(
                datetime.utcfromtimestamp(int(xml.xpath('/WA/RESOLUTION/IMPLEMENTED')[0].text)),
                'UTC'
            ).astimezone(timezone('US/Eastern')),  # convert to eastern time
            chamber=clean_chamber_input(xml.xpath('/WA/RESOLUTION/COUNCIL')[0].text)[1],

            category=capitalise(xml.xpath('/WA/RESOLUTION/CATEGORY')[0].text),
            strength=capitalise(
                _translate_category(
                    xml.xpath('/WA/RESOLUTION/CATEGORY')[0].text,  # category
                    xml.xpath('/WA/RESOLUTION/OPTION')[0].text  # option
                )[1]  # get name
            ),

            is_repealed=resolution_is_repealed,
            repealed_by=int(xml.xpath('/WA/RESOLUTION/REPEALED_BY')[0].text) if resolution_is_repealed else None,
            is_repeal=resolution_is_a_repeal,
            repeals=int(xml.xpath('/WA/RESOLUTION/REPEALS_COUNCILID')[0].text) if resolution_is_a_repeal else None,

            # text and author
            text=resolution_text.strip(),
            author=author.strip(),

            # vote data
            votes_for=int(xml.xpath('/WA/RESOLUTION/TOTAL_VOTES_FOR')[0].text),
            votes_against=int(xml.xpath('/WA/RESOLUTION/TOTAL_VOTES_AGAINST')[0].text)
        )

        assert resolution.strength != '0', 'resolution {} has strength 0 with category {}'.format(
            resolution.title, resolution.category
        )

        # overwrite category if repeal with the repeals field; NS API is broken sometimes for some reason
        if resolution_is_a_repeal:
            resolution.strength = str(int(resolution.repeals))  # cast to integer

        # check for co-authors
        coauth_list = xml.xpath('/WA/RESOLUTION/COAUTHOR/N')
        if len(coauth_list) != 0:
            print('received from API coauthors: {}'.format(
                ', '.join([capitalise(n.text) for n in coauth_list])
            ))

            try:
                resolution.coauthor0 = capitalise(coauth_list[0].text)
            except IndexError:
                pass

            try:
                resolution.coauthor1 = capitalise(coauth_list[1].text)
            except IndexError:
                pass

            try:
                resolution.coauthor2 = capitalise(coauth_list[2].text)
            except IndexError:
                pass

        else:
            cleaned_resolution_text = resolution_text \
                .replace('[i]', '').replace('[/i]', '') \
                .replace('[b]', '').replace('[/b]', '') \
                .replace('[u]', '').replace('[/u]', '')
            coauthor_matches = [s for s in cleaned_resolution_text.splitlines()
                                if re.search(
                    r'(Co-?((Author(ed)?:?)|written|writer) ?(by|with)? ?:?)|'
                    r'(This resolution includes significant contributions made by\s+)',
                    s, re.IGNORECASE
                )]
            if len(coauthor_matches) > 0:
                coauthor_line = re.sub(r'Co-?((Author(ed)?:?)|written|writer) ?(by|with)? ?:? ', repl='',
                                       string=coauthor_matches[0], flags=re.IGNORECASE)
                print(f'\tidentified coauthor line: "{coauthor_line}"')
                coauthor_line = coauthor_line \
                    .replace('[i]', '') \
                    .replace('[/i]', '') \
                    .replace('[b]', '') \
                    .replace('[/b]', '') \
                    .replace('[u]', '') \
                    .replace('[/u]', '')

                if '[nation' in coauthor_line.lower():  # scion used the [Nation] tag instead of lower case once
                    amended_line = re.sub(r'(?<=\[nation)=(.*?)(?=\])', '', coauthor_line.lower())  # remove 'noflag' etc
                    coauthors = re.findall(r'(?<=\[nation\])(.*?)(?=\[/nation\])', amended_line.lower())

                else:
                    # this will break with names like "Sch'tz and West Runk'land"
                    coauthors = re.split(r'(,? and )|(, )', coauthor_line, re.IGNORECASE)
                    coauthors = [i for i in coauthors if i is not None and i.strip() != 'and']  # post facto patching...

                coauthors = [ref(s).replace('.', '') for s in coauthors]  # cast to reference name
                print(f'\tidentified coauthors as {coauthors}')

                # pass each co-author in turn
                '''
                While it could be changed so that the original line's capitalisation is preserved, doing this might 
                introduce inconsistency in capitalisation of the same nation. Eg '[nation]imperium_anglorum[/nation]' would
                be done under capitalisation rules while something provided as 'Imperium ANGLORUM' would be let through.
                
                Because some authors use a ref'd name IN the nation tags, something like [nation]transilia[/nation] cannot
                be disentangled from 'Transilia' if the former is proper and the latter is not. A proper-capitalisation
                dictionary would be necessary and I am unwilling to download and parse all historical daily dumps for 
                something this minor. 
                '''
                try:
                    resolution.coauthor0 = capitalise(coauthors[0])
                except IndexError:
                    pass

                try:
                    resolution.coauthor1 = capitalise(coauthors[1])
                except IndexError:
                    pass

                try:
                    resolution.coauthor2 = capitalise(coauthors[2])
                except IndexError:
                    pass

        cacher.save()
        return resolution


def get_count() -> int:
    soup = BeautifulSoup(call_api('http://forum.nationstates.net/viewtopic.php?f=9&t=30'), 'lxml')
    resolution = soup.select('div#p310 div.content a')
    return len(resolution)


def parse() -> 'pd.DataFrame':
    # find the number of resolutions from Passed GA Resolutions
    passed_res_max = get_count()
    print(f'found {passed_res_max} resolutions')

    # confirm that we have X resolutions
    res_list = []
    max_res = -1
    for i in range(passed_res_max - 1, passed_res_max + 20):  # passed resolutions should never be more than 20 behind
        try:
            print(f'gettingGA {i + 1} of {passed_res_max} predicted resolutions')
            d = WaPassedResolution.parse_ga(i + 1).__dict__  # note that 0 returns resolution at vote, need to 1-index
            res_list.append(d)
        except ValueError:
            print('out of resolutions; data should be complete')
            max_res = i
            break

    print(f'found {max_res} resolutions; getting historical')

    # get API information for each resolution
    for i in reversed(range(0, passed_res_max - 1)):  # passed_res_max is already called above
        print(f'got {max_res - passed_res_max + i} of {max_res} resolutions')
        print(f'getting GA {i + 1}')
        r = WaPassedResolution.parse_ga(i + 1)  # note that 0 returns resolution at vote, need to 1-index
        d = r.__dict__  # hacky cheating to get into dict
        res_list.append(d)

    # put it up in pandas
    df = pd.DataFrame(res_list).replace({None: np.nan})
    df.drop(columns=['text'], inplace=True)
    df.rename(columns={
        'council': 'Council',  # Auralia used these names for columns
        'resolution_num': 'Number',
        'title': 'Title',
        'category': 'Category',
        'strength': 'Sub-category',
        'votes_for': 'Votes For',
        'votes_against': 'Votes Against',
        'implementation': 'Date Implemented',
        'author': 'Author'
    }, inplace=True)
    df.sort_values(by='Number', inplace=True)

    def join_coauthors(coauthor_list, j=', '):
        """ Removes empty/whitespace-only strings and then joins """
        authors = [s for s in coauthor_list if s.strip() != '']
        return j.join(authors)

    df['Co-authors'] = df[['coauthor0', 'coauthor1', 'coauthor2']] \
        .replace({np.nan: ''}) \
        .agg(join_coauthors, axis=1)

    assert all(df['Sub-category'] != '0'), 'resolutions {} have sub-category 0'.format(
        df.loc[df['Sub-category'] != '0', 'Title'].values
    )

    return df[['Number', 'Title', 'Category', 'Sub-category', 'Author', 'Co-authors',
               'Votes For', 'Votes Against', 'Date Implemented']].copy()  # take only relevant vars
