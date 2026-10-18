#!/usr/bin/env python3
"""Lint the course retelling in skills/nif/references/ (and any extra public file).

  python3 tools/check_refs.py                     # references/ + index.json, full rules
  python3 tools/check_refs.py --files a.md b.html  # banned words and quotes only
      [--allow REGEX ...] [--quote-words N]       # e.g. the plugin's own name in install lines

Errors (exit 1):
  - personal or private markers: the owner's system name, task manager, home paths, Obsidian
    links and wikilinks, cloud-drive names, the 2023 materials, years 2023–2029 outside the course
    title, dd.mm dates;
  - source-place markers of the original materials (slide numbers, transcript, mind map);
  - a «…» quote longer than 6 words (the references retell, they do not quote);
  - references only: missing frontmatter fields, unknown kind, broken relative links, index.json
    out of sync with the files, a file over 12 000 characters.
"""
import argparse, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(ROOT, 'skills', 'nif', 'references')
KINDS = {'overview', 'lesson', 'practice', 'sprint-day', 'protocol', 'glossary'}
MAX_CHARS = 12000
BANNED = [
    (re.compile(r'jadlis', re.I), 'owner system name'),
    (re.compile(r'tick\s?tick', re.I), 'task manager'),
    (re.compile(r'/Users/|~/'), 'home path'),
    (re.compile(r'obsidian://', re.I), 'obsidian link'),
    (re.compile(r"\[\[(?=[^\]'\"\[\d\s])"), 'wikilink'),
    (re.compile(r'icloud|mobile documents', re.I), 'cloud drive'),
    (re.compile(r'итоги\s+года', re.I), '2023 materials'),
    (re.compile(r'sw\.?band', re.I), '2023 materials'),
    (re.compile(r'(?<!интеграция )(?<!integration )\b202[3-9]\b', re.I), 'year outside the course title'),
    (re.compile(r'(?<![\d.])\d{2}\.\d{2}(?![\d])(?!\s*%)'), 'dd.mm date'),
    (re.compile(r'\(сл\.|\bсл\.\s*\d|расшифровк|майндкарт|mind-?карт', re.I), 'source-place marker'),
]
QUOTE = re.compile(r'«([^«»]+)»')
LINK = re.compile(r'(?<![\w/.-])((?:lessons|practices|protocols|sprint|glossary)/[a-z0-9-]+\.md|program\.md|zones\.md|science\.md)')


def norm(s):
    return unicodedata.normalize('NFC', s)


def frontmatter(text):
    if not text.startswith('---\n'):
        return None, text
    end = text.find('\n---', 4)
    if end < 0:
        return None, text
    fm = {}
    for line in text[4:end].splitlines():
        m = re.match(r'^([a-z_]+):\s*(.*)$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"')
    return fm, text[end + 4:]


def lint_text(path, text, problems, allow=(), quote_words=6):
    for i, line in enumerate(text.splitlines(), 1):
        for rx in allow:
            line = rx.sub(' ', line)
        for rx, why in BANNED:
            m = rx.search(line)
            if m:
                problems.append('%s:%d: %s: %r' % (path, i, why, m.group(0)))
        for q in QUOTE.findall(line):
            if len(re.findall(r'\w+', q)) > quote_words:
                problems.append('%s:%d: quote longer than %d words: «%s»' % (path, i, quote_words, q[:80]))


def lint_refs(problems):
    files = []
    for dp, _, fn in os.walk(REFS):
        for f in fn:
            if f.endswith('.md'):
                files.append(norm(os.path.relpath(os.path.join(dp, f), REFS)))
    files.sort()
    ids = {}
    for rel in files:
        p = os.path.join(REFS, rel)
        text = norm(open(p, encoding='utf-8').read())
        lint_text('references/' + rel, text, problems)
        if len(text) > MAX_CHARS:
            problems.append('references/%s: %d chars > %d' % (rel, len(text), MAX_CHARS))
        fm, body = frontmatter(text)
        if fm is None:
            problems.append('references/%s: no frontmatter' % rel)
            continue
        for k in ('id', 'title', 'kind', 'cite'):
            if not fm.get(k):
                problems.append('references/%s: frontmatter lacks %s' % (rel, k))
        if fm.get('kind') and fm['kind'] not in KINDS:
            problems.append('references/%s: unknown kind %s' % (rel, fm['kind']))
        if fm.get('id') in ids:
            problems.append('references/%s: duplicate id %s (also %s)' % (rel, fm['id'], ids[fm['id']]))
        ids[fm.get('id')] = rel
        for link in set(LINK.findall(text)):
            if not os.path.exists(os.path.join(REFS, link)):
                problems.append('references/%s: broken link %s' % (rel, link))
    idx_path = os.path.join(REFS, 'index.json')
    if not os.path.exists(idx_path):
        problems.append('references/index.json missing (run tools/build_index.py)')
        return len(files)
    idx = json.load(open(idx_path, encoding='utf-8'))
    listed = {e['file'] for e in idx['files']}
    for rel in sorted(set(files) - listed):
        problems.append('references/index.json: %s not listed' % rel)
    for rel in sorted(listed - set(files)):
        problems.append('references/index.json: lists missing %s' % rel)
    return len(files)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--files', nargs='+', help='lint these files with the banned-word and quote rules only')
    ap.add_argument('--allow', action='append', default=[], help='regex removed from each line before the checks')
    ap.add_argument('--quote-words', type=int, default=6)
    a = ap.parse_args(argv)
    problems = []
    if a.files:
        allow = [re.compile(x) for x in a.allow]
        for f in a.files:
            lint_text(f, norm(open(f, encoding='utf-8').read()), problems, allow, a.quote_words)
        n = len(a.files)
    else:
        n = lint_refs(problems)
    for p in problems:
        print(p)
    print('checked %d files, %d problems' % (n, len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
