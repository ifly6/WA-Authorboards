# Copyright (c) 2020 ifly6
import json
from functools import cache


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

    def save(self, path='../db/api_cache.json'):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.d, f, ensure_ascii=False, indent=4)

    @staticmethod
    def load(path='../db/api_cache.json'):
        with open(path, 'r') as f:
            d = json.load(f)
            return Cacher(d)


@cache
def load_capitalisation_exceptions(p='../db/names.txt'):
    """ Cached to reduce disk IO times on repeated calls. Data here should not change. """
    with open(p, 'r') as f:
        return set(f.readlines())
