import pandas as pd

from src.load_db import Database


def _count(g):
    return sum(1 for _ in g)


def create_leaderboards(db: Database):
    l = []
    for author in (db.authors + db.player_authors):
        d = {'Name': author.name if author.is_player == False else '[PLAYER] ' + author.name,
             'Authored': len(author.authored_resolutions),
             'Co-authored': len(author.coauthored_resolutions),
             'Repeals': _count(r for r in author.authored_resolutions if r.category in ["Repeal", 'repeal']),
             'Active': _count(r for r in author.authored_resolutions + author.coauthored_resolutions
                              if r.repealed_by is None and r.category not in ['Repeal', 'repeal'])}
        l.append(d)

    df = pd.DataFrame(l)

    # create totals and sort
    df['Total'] = df['Authored'] + df['Co-authored']
    df.sort_values(by=['Total', 'Name'], ascending=[False, True], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df.to_markdown()
