# Copyright (c) 2020 ifly6
import pandas as pd

from src.load_db import Database


def _count(g):
    return sum(1 for _ in g)


def _flatten(l):
    return [item for sublist in l for item in sublist]


def df_to_bbcode(df, column_predicate={}):
    lines = [''.join('[td]{}[/td]'.format(str(s)) for s in df.columns)]  # init with header
    for _, row in df.iterrows():
        cells = ''.join('[td]{}[/td]'.format(str(s)) for s in row.values)
        lines.append(cells)

    out = '[table]' + ''.join('[tr]{}[/tr]'.format(s) for s in lines) + '[/table]'
    return out.replace('\n', '')


def _get_aliases(path='../db/aliases.csv', how='flat'):
    alias_df = pd.read_csv(path)
    if how == 'flat':
        aliases = set(_flatten(alias_df['Aliases'].str.split(',').values) + list(alias_df['Player'].values))
        return aliases
    if how == 'dict':
        alias_df.set_index('Player', inplace=True)
        return alias_df['Aliases'].str.split(',').to_dict()
    if how == 'pandas':
        return alias_df
    raise ValueError(f'input, {how}, invalid')


def create_aliases(alias_path='', how='markdown'):
    aliases = _get_aliases(how='pandas') \
        if alias_path == '' \
        else _get_aliases(path=alias_path, how='pandas')
    aliases['Aliases'] = aliases['Aliases'].str.replace(r'\s*,\s*', ', ', regex=True)
    aliases.sort_values(by='Player', ascending=True, inplace=True)

    if how == 'markdown':
        return aliases.to_markdown(index=False)

    if how == 'bbCode' or how == 'bbcode':
        aliases['Player'] = '[nation]' + aliases['Player'].astype(str) + '[/nation]'
        return df_to_bbcode(aliases)

    raise ValueError(f'input, {how}, invalid')


def create_leaderboards(db: Database, how='markdown', keep_puppets=True):
    # concat needs list
    rows = []
    for author in (db.authors + db.player_authors):
        if author.is_player is False and author.name in _get_aliases() and keep_puppets is False:
            continue  # if not keeping puppets, skip non-players who match alias list

        d = {'Name': '[PLAYER] ' + author.name if author.is_player else author.name,
             'Authored': len(author.authored_resolutions),
             'Co-authored': len(author.coauthored_resolutions),
             'Repeals': _count(r for r in author.authored_resolutions if r.category in ["Repeal", 'repeal']),
             'Active': _count(r for r in author.authored_resolutions + author.coauthored_resolutions
                              if r.repealed_by is None and r.category not in ['Repeal', 'repeal'])}
        rows.append(d)
    df = pd.DataFrame(rows)

    # create totals and sort
    df['Total'] = df['Authored'] + df['Co-authored']
    df.sort_values(by=['Total', 'Name'], ascending=[False, True], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # create ranking, but only if enumerating players
    if keep_puppets is False:
        df.insert(0, 'Rank', '')
        for i, row in df.iterrows():
            try:
                same_total = row['Total'] == df.loc[i - 1, 'Total']
            except KeyError:
                same_total = False

            df.loc[i, 'Rank'] = (df.loc[i - 1, 'Rank'] if same_total
                                 else i + 1)

    # output
    if how == 'pandas':
        return df

    if how == 'markdown':
        df['Name'] = df['Name'].str.replace(r'\[PLAYER\]', r'**[PLAYER]**', regex=True)
        return df.to_markdown(index=False)

    if how == 'bbCode' or how == 'bbcode':
        df['Name'] = '[nation]' + df['Name'].astype(str) + '[/nation]'
        return df_to_bbcode(df)

    if how == 'string' or how == 'str':
        return df.to_string(index=False)

    if how == 'latex':
        return df.to_latex(index=False)

    raise ValueError(f'format string, {how}, invalid')
