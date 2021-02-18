# Copyright (c) 2017 Auralia
# Modifications, copyright (c) 2020 ifly6
import csv
from datetime import datetime


def is_same_name(i, a):
    return i.lower().strip() == a.lower().strip()


class Database:
    def __init__(self):
        self.resolutions = []
        self.authors = []
        self.player_authors = []
        self.aliases = {}

    @staticmethod
    def create(resolutions_path, aliases_path):
        db = Database()
        db.parse_resolutions(resolutions_path)
        db.parse_aliases(aliases_path)
        return db

    def parse_resolutions(self, path):
        with open(path) as csv_file:
            next(csv_file)
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                self.resolutions.append(Resolution(self, *row))

    def parse_aliases(self, path):
        with open(path) as csv_file:
            next(csv_file)
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                player_name = row[0]

                # create dict entry k=player_name, v=[aliases..., main_name]
                aliases = [s.strip() for s in row[1].split(",")]
                aliases.append(player_name)
                self.aliases[player_name] = aliases

                player = Author(player_name, is_player=True)

                # for all resolutions, construct alias data
                for res in self.resolutions:
                    for alias in aliases:
                        if is_same_name(alias, res.author.name):
                            player.authored_resolutions.append(res)
                            res.player_author = player

                        elif any(is_same_name(alias, r.name) for r in res.coauthors):
                            # ^ case insensitive check
                            # OG: elif alias.lower() in [r.name.lower() for r in resolution.coauthors]:
                            player.coauthored_resolutions.append(res)
                            res.player_coauthors.append(player)

                self.player_authors.append(player)


class Author:
    def __init__(self, name, is_player=False):
        self.name = name
        self.is_player = is_player

        self.authored_resolutions = []
        self.coauthored_resolutions = []

    def __str__(self):
        return self.name


class Resolution:
    def __init__(self, db: Database, number: str, title: str, category: str,
                 subcategory: str, author_name: str, coauthor_names: str,
                 votes_for: str, votes_against: str, date: str):
        self.db = db
        self.number = int(number)
        self.title = title
        self.category = category
        self.subcategory = subcategory

        if self.category == "Repeal":
            repeal_number = int(self.subcategory)
            for res in db.resolutions:
                if res.number == int(self.subcategory):
                    self.repeal = res
                    res.repealed_by = self
                    break

            else:  # if no resolution was found
                if int(self.number) < int(self.subcategory):
                    raise RuntimeError(f'Resolution number is less than the number of the resolution this is '
                                       f'supposedly repealing (num={self.number}; subcat={self.subcategory})')
                else:
                    raise RuntimeError(f"Error processing resolution {number}:"
                                       f" no resolution found with number"
                                       f" {repeal_number}")
        else:
            self.repeal = None

        # get or create authors
        for a in db.authors:
            if is_same_name(a.name, author_name):
                self.author = a
                break
        else:
            self.author = Author(author_name.strip())
            db.authors.append(self.author)

        self.author.authored_resolutions.append(self)

        # get or create co-authors
        self.coauthors = []
        for coauthor_name in [s.strip() for s in coauthor_names.split(",")]:
            if coauthor_name == "":
                continue

            for a in db.authors:
                if is_same_name(a.name, coauthor_name):
                    coauthor = a
                    self.coauthors.append(a)
                    break
            else:
                coauthor = Author(coauthor_name)
                self.coauthors.append(coauthor)
                db.authors.append(coauthor)

            coauthor.coauthored_resolutions.append(self)

        self.votes_for = int(votes_for)
        self.votes_against = int(votes_against)

        self.date = datetime.strptime(
            date if ' ' not in date else date[:date.index(' ')],  # if date has time info at the end cut it off
            "%Y-%m-%d"
        )

        self.repealed_by = None  # this is safe because it will be overwritten when parsing the repeal
        self.player_author = None  # constructed when aliases are parsed
        self.player_coauthors = []

    def __str__(self):
        return self.title
