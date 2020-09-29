def write_file(path, s):
    path = path + '.txt' if not path.endswith('.txt') else path
    with open(path, 'w') as f:
        f.write(s)
