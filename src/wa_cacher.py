# Copyright (c) 2020 ifly6
import glob
import json
from datetime import datetime
from functools import cache
from json import JSONDecodeError
from os.path import getsize


class Cacher(object):
    """ Caches all the API responses and persists it as `api_cache.json`. If you want to re-pull that data, delete the
    cache file and it will do that automatically. """

    def __init__(self, d=None):
        if d is None:
            d = {}  # stupid python

        self.d = d

    def contains(self, key):
        return key in self.d

    def get(self, key):
        return self.d[key]

    def update(self, k, v):
        self.d[k] = v

    def save(self, path=None):
        if path is None:
            path = '../db/cache/api_cache_{}.json'.format(datetime.now().strftime('%Y-%m-%d'))

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.d, f, ensure_ascii=False, indent=4)

    @staticmethod
    def load(path=None, attempt=0):
        if path is None:
            fs = glob.glob('../db/cache/api_cache*.json')
            fs.sort(key=getsize, reverse=True)  # get largest json
            path = fs[0 + attempt]  # get next largest if the largest doesn't work, don't use `max(fs, key=getsize)`

        with open(path, 'r') as f:
            try:
                d = json.load(f)
                return Cacher(d)
            except JSONDecodeError as e:
                if attempt == 0:
                    return Cacher.load(attempt=1)
                else:
                    # rethrow error if on second try it doesn't work
                    raise e


@cache
def load_capitalisation_exceptions(p='../db/names.txt'):
    """ Cached to reduce disk IO times on repeated calls. Data here should not change. """
    with open(p, 'r') as f:
        return set(f.readlines())
