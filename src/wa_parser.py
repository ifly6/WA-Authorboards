import html
import io
import re
from datetime import datetime
from typing import Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree
from pytz import timezone
from ratelimit import rate_limited

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


@rate_limited(35, 30)
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


def as_ref_name(s: str) -> str:
    """ Turn it into a NationStates ref name """
    return s.strip().replace(' ', '_').lower()


def _translate_category(category: str, s: str) -> Tuple[bool, str]:
    if s != '0':
        # if it isn't 0, then it doesn't apply
        return False, s

    d = {'Advancement of Industry': 'Environmental Deregulation',
         'Civil Rights': 'Mild',
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
         'Social Justice': 'Mild'}
    d = {as_ref_name(k): v for k, v in d.items()}  # force ref name for matching

    try:
        return True, d[as_ref_name(category)]  # yield correct name from ref name of category
    except KeyError:
        return False, s  # if not in the list, what is given


def capitalise(s):
    s = s.replace('_', ' ').strip()

    # exceptions
    capitalisation_exceptions = wa_cacher.load_capitalisation_exceptions()
    for i in capitalisation_exceptions:
        if s.lower() == i.lower():
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

        self.__dict__.update(kwargs)  # django does this automatically, i'm not updating it; lazy

    @staticmethod
    def parse_ga(res_num):

        from src.wa_cacher import Cacher
        try:
            cacher = Cacher.load()
        except FileNotFoundError:
            cacher = Cacher()  # init new

        api_url = 'https://www.nationstates.net/cgi-bin/api.cgi?wa=1&id={}&q=resolution'.format(res_num)
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
            text=resolution_text,
            author=author,

            # vote data
            votes_for=int(xml.xpath('/WA/RESOLUTION/TOTAL_VOTES_FOR')[0].text),
            votes_against=int(xml.xpath('/WA/RESOLUTION/TOTAL_VOTES_AGAINST')[0].text)
        )

        # overwrite category if repeal with the repeals field; NS API is broken sometimes for some reason
        if resolution_is_a_repeal:
            resolution.strength = str(int(resolution.repeals))  # cast to integer

        # check for co-authors
        coauthor_matches = [s for s in resolution_text.splitlines()
                            if re.search(r'Co-?((Author(ed)?:?)|written|writer) ?(by|with)? ?:? ', s, re.IGNORECASE)]
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
                amended_line = re.sub(r'(?<=\[nation)\=(.*?)(?=\])', '', coauthor_line.lower())
                coauthors = re.findall(r'(?<=\[nation\])(.*?)(?=\[\/nation\])', amended_line.lower())

            else:
                # this will break with names like "Sch'tz and West Runk'land"
                coauthors = re.split(r'(,? and )|(, )', coauthor_line, re.IGNORECASE)
                coauthors = [i for i in coauthors if i is not None and i.strip() != 'and']  # post facto patching...

            coauthors = [as_ref_name(s).replace('.', '') for s in coauthors]  # cast to reference name
            print(f'\tidentified coauthors as {coauthors}')

            # pass each co-author in turn
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


def parse():
    # find the number of resolutions from Passed GA Resolutions
    reslist = []
    soup = BeautifulSoup(call_api('http://forum.nationstates.net/viewtopic.php?f=9&t=30'), 'lxml')
    resolution = soup.select('div#p310 div.content a')
    resolution_number = len(resolution)
    print(f'found {resolution_number} resolutions')

    # get API information for each resolution
    i = 1
    for i in range(resolution_number + 20):  # passed resolutions should never be more than 20 behind... hopefully
        try:
            print(f'calling for GA {i + 1} of {resolution_number} predicted resolutions')
            d = WaPassedResolution.parse_ga(i + 1).__dict__  # note that 0 returns resolution at vote, need to 1-index
            reslist.append(d)
        except ValueError:
            print('out of resolutions; data should be complete')
            break

    # put it up in pandas
    df = pd.DataFrame(reslist).replace({None: np.nan})
    df.drop(columns=['text'], inplace=True)
    df.rename(columns={
        'resolution_num': 'Number',  # Auralia used these names for columns
        'title': 'Title',
        'category': 'Category',
        'strength': 'Sub-category',
        'votes_for': 'Votes For',
        'votes_against': 'Votes Against',
        'implementation': 'Date Implemented',
        'author': 'Author'
    }, inplace=True)

    def join_coauthors(l, j=', '):
        """ Removes empty/whitespace-only strings and then joins """
        authors = [s for s in l if s.strip() != '']
        return j.join(authors)

    df['Co-authors'] = df[['coauthor0', 'coauthor1', 'coauthor2']] \
        .replace({np.nan: ''}) \
        .agg(join_coauthors, axis=1)

    return df[['Number', 'Title', 'Category', 'Sub-category', 'Author', 'Co-authors',
               'Votes For', 'Votes Against', 'Date Implemented']].copy()  # take only relevant vars
