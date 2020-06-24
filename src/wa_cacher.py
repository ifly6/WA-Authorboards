import json


class Cacher(object):

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
