#!/usr/bin/env python3
"""Rebuild skills/nif/references/index.json from the frontmatter of the reference files.

  python3 tools/build_index.py [--check]   # --check: exit 1 when index.json is out of date
"""
import argparse, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(ROOT, 'skills', 'nif', 'references')
ORDER = ['overview', 'lesson', 'protocol', 'practice', 'sprint-day', 'glossary']
N = lambda s: unicodedata.normalize('NFC', s)


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    out = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        mm = re.match(r'^([a-z_]+):\s*(.*?)\s*$', line)
        if not mm:
            continue
        v = mm.group(2)
        if v.startswith('[') and v.endswith(']'):
            v = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        else:
            v = v.strip('"\'')
        out[mm.group(1)] = v
    return out


def sort_key(e):
    kind = ORDER.index(e['kind']) if e['kind'] in ORDER else len(ORDER)
    nums = tuple(int(x) for x in re.findall(r'\d+', e['file'])) or (999,)
    return (kind, nums, e['file'])


def build():
    files = []
    for dp, _, fn in os.walk(REFS):
        for f in fn:
            if not f.endswith('.md'):
                continue
            p = os.path.join(dp, f)
            rel = N(os.path.relpath(p, REFS))
            text = N(open(p, encoding='utf-8').read())
            fm = frontmatter(text)
            e = dict(file=rel, id=fm.get('id', ''), title=fm.get('title', ''), kind=fm.get('kind', ''),
                     cite=fm.get('cite', ''), chars=len(text))
            if fm.get('week'):
                e['week'] = int(fm['week']) if str(fm['week']).isdigit() else fm['week']
            for k in ('keywords', 'related'):
                if fm.get(k):
                    e[k] = fm[k] if isinstance(fm[k], list) else [fm[k]]
            files.append(e)
    files.sort(key=sort_key)
    return dict(files=files)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    idx = build()
    path = os.path.join(REFS, 'index.json')
    new = json.dumps(idx, ensure_ascii=False, indent=1) + '\n'
    if a.check:
        try:
            old = open(path, encoding='utf-8').read()
        except OSError:
            old = ''
        if old != new:
            print('index.json is out of date: run python3 tools/build_index.py')
            return 1
        print('index.json up to date (%d files)' % len(idx['files']))
        return 0
    open(path, 'w', encoding='utf-8').write(new)
    print('wrote %s (%d files, %d chars total)' % (os.path.relpath(path, ROOT), len(idx['files']),
                                                  sum(e['chars'] for e in idx['files'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
