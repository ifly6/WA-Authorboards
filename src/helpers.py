def write_file(path, s):
    if not path.endswith('.txt'):
        if not path.endswith('.md'):
            path = path + '.txt'

    with open(path, 'w') as f:
        f.write(s)
