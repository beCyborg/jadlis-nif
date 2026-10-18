#!/usr/bin/env python3
"""Build the NIF atlas page from atlas.src.html.

  python3 build_atlas.py --share --out build/share                      # public version
  python3 build_atlas.py --personal path/to/atlas-personal.json --out build/personal
  ... [--audio DIR]   # also link DIR as <out>/audio for a local preview

Source markers:
  <!--@if share-->…<!--@endif-->           kept only in the public build (also @if personal)
  <!--@slot:name-->default<!--@endslot-->  the personal build may replace the default with slots[name]
  <!--@move:name-->…<!--@endmove-->        the public build moves this block to <!--@put:name-->
  /*@BUILD*/{…}/*@END*/                     page config; the personal build passes its JSON (without slots)
The personal JSON never enters this repository.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
IF = re.compile(r'<!--@if (share|personal)-->(.*?)<!--@endif-->', re.S)
SLOT = re.compile(r'<!--@slot:(\w+)-->(.*?)<!--@endslot-->', re.S)
BUILD = re.compile(r'/\*@BUILD\*/.*?/\*@END\*/', re.S)
MOVE = re.compile(r'<!--@move:(\w+)-->(.*?)<!--@endmove-->', re.S)
PUT = re.compile(r'<!--@put:(\w+)-->')


def move_blocks(out, share):
    blocks = dict((m.group(1), m.group(2)) for m in MOVE.finditer(out))
    puts = PUT.findall(out)
    if sorted(blocks) != sorted(puts):
        raise SystemExit('@move and @put do not match: %s vs %s' % (sorted(blocks), sorted(puts)))
    out = MOVE.sub(lambda m: '' if share else m.group(2), out)
    return PUT.sub(lambda m: blocks[m.group(1)] if share else '', out)


def build(src, personal=None):
    mode = 'personal' if personal else 'share'
    out = IF.sub(lambda m: m.group(2) if m.group(1) == mode else '', src)
    out = move_blocks(out, personal is None)
    slots = (personal or {}).get('slots') or {}
    out = SLOT.sub(lambda m: slots.get(m.group(1), m.group(2)), out)
    cfg = dict((k, v) for k, v in (personal or {}).items() if k != 'slots')
    cfg['share'] = personal is None
    js = json.dumps(cfg, ensure_ascii=False).replace('</', '<\\/')
    out, n = BUILD.subn(lambda m: js, out)
    if n != 1:
        raise SystemExit('expected one /*@BUILD*/ marker, found %d' % n)
    left = re.findall(r'<!--@\w+|/\*@\w+', out)
    if left:
        raise SystemExit('unprocessed markers: %s' % sorted(set(left)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--share', action='store_true')
    g.add_argument('--personal', metavar='JSON')
    ap.add_argument('--src', default=os.path.join(HERE, 'atlas.src.html'))
    ap.add_argument('--out', required=True, help='output folder; the page is written as index.html')
    ap.add_argument('--audio', help='folder with the mp3 clips to link as <out>/audio')
    a = ap.parse_args(argv)
    src = open(a.src, encoding='utf-8').read()
    personal = json.load(open(os.path.expanduser(a.personal), encoding='utf-8')) if a.personal else None
    html = build(src, personal)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, 'index.html')
    open(path, 'w', encoding='utf-8').write(html)
    if a.audio:
        link = os.path.join(a.out, 'audio')
        if os.path.islink(link):
            os.remove(link)
        if not os.path.exists(link):
            os.symlink(os.path.abspath(os.path.expanduser(a.audio)), link)
    print('%s: %s (%d chars)' % ('personal' if personal else 'share', path, len(html)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
