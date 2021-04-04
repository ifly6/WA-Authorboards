# Copyright (c) 2020 ifly6
def write_file(path, s, print_input=False):
    if print_input: print(s)

    if not path.endswith('.txt'):
        if not path.endswith('.md'):
            path = path + '.txt'

    with open(path, 'w') as f:
        f.write(s)


def ref(s: str) -> str:
    """ Turn it into a NationStates ref name """
    return s.strip().replace(' ', '_').lower()


assert ref('IMPERIUM ANGLORUM  ') == 'imperium_anglorum'
