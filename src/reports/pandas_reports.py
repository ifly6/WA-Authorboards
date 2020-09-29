import pandas as pd

from src.load_db import Database


def _count(g):
    return sum(1 for _ in g)


def __create_leaderboard_df(db: Database):
    l = []
    for author in (db.authors + db.player_authors):
        d = {'Name': '[PLAYER] ' + author.name if author.is_player else author.name,
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
    return df


def create_leaderboards(db: Database, format='markdown'):
    df = __create_leaderboard_df(db)

    if format == 'markdown':
        df['Name'] = df['Name'].str.replace(r'\[PLAYER\]', r'**[PLAYER]**')
        return df.to_markdown(index=False)

    if format == 'bbCode':
        lines = [''.join('[td]{}[/td]'.format(str(s)) for s in df.columns)]  # init with header
        df['Name'] = df['Name'].apply(lambda s: '[nation]{}[/nation]'.format(s))

        for i, row in df.iterrows():
            cells = ''.join('[td]{}[/td]'.format(str(s)) for s in row.values)
            lines.append(cells)

        return '[table]' + ''.join('[tr]{}[/tr]'.format(s) for s in lines) + '[/table]'

    if format == 'string' or format == 'str':
        return df.to_string(index=False)

    if format == 'latex':
        return df.to_latex(index=False)
