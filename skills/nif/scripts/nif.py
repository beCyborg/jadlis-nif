#!/usr/bin/env python3
"""Sprint position, lesson progress, search and journal for the /nif skill. Stdlib only, Python 3.9+.

  nif.py [--data DIR] [--profile FILE] where [--date YYYY-MM-DD] [--sprint-start D [--sprint-in-quarter N] [--audio yes|no]]
  nif.py [--data DIR] setup --sprint-start YYYY-MM-DD [--sprint-in-quarter 1|2|3] [--audio yes|no]
  nif.py [--data DIR] progress show | mark 1.4 2.6 ... | unmark 1.4
  nif.py find "<question words>" [--limit 5]
  nif.py show <id | path>                      # L1.4, P05, D03, PR-sane, G-stress, program, zones, science
  nif.py [--profile FILE] link <id | note name> ...   # Obsidian links, only with a profile that names a vault
  nif.py [--data DIR] log add --zone Z [--practice P] [--note TEXT] | log show [--days 7]
  nif.py [--data DIR] note add TEXT | note show
  nif.py [--data DIR] [--profile FILE] state

Output is JSON except `show`. State lives in --data; when it is empty or unexpanded, in
$CLAUDE_PLUGIN_DATA; otherwise in <config dir>/plugins/data/jadlis-nif-jadlis.
"""
import argparse, datetime as dt, json, os, re, shlex, subprocess, sys, unicodedata, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.normpath(os.path.join(HERE, '..', 'references'))
SPRINT_DAYS = 21
NO_AUDIO = {7, 14, 21}
REFLECTION_DAYS = {6, 13, 20}
WEEKDAY = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
WHERE_CMD_TIMEOUT = 15
N = lambda s: unicodedata.normalize('NFC', s)


# ---------- paths, state, profile ----------

def unexpanded(v):
    return not v or '${' in v


def data_dir(arg):
    if not unexpanded(arg):
        return os.path.expanduser(arg)
    env = os.environ.get('CLAUDE_PLUGIN_DATA')
    if not unexpanded(env):
        return os.path.expanduser(env)
    cfg = os.environ.get('CLAUDE_CONFIG_DIR') or '~/.claude'
    return os.path.join(os.path.expanduser(cfg), 'plugins', 'data', 'jadlis-nif-jadlis')


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n?', text, re.S)
    if not m:
        return {}, text
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'^([A-Za-z_][\w-]*):\s*(.*?)\s*$', line)
        if not mm:
            continue
        v = mm.group(2)
        if v.startswith('[') and v.endswith(']'):
            v = [x.strip().strip('"\'') for x in v[1:-1].split(',') if x.strip()]
        else:
            v = v.strip('"\'')
        out[mm.group(1)] = v
    return out, text[m.end():]


def load_profile(arg):
    path = arg if not unexpanded(arg) else os.environ.get('NIF_PROFILE', '')
    if unexpanded(path):
        return None
    path = os.path.expanduser(path)
    try:
        text = N(open(path, encoding='utf-8').read())
    except OSError as e:
        return dict(path=path, error='profile not readable: %s' % e.strerror)
    fm, _ = frontmatter(text)
    return dict(path=path, fields=fm)


# ---------- reference index ----------

def index(refs=REFS):
    idx = load_json(os.path.join(refs, 'index.json'), None)
    if idx is None:
        raise SystemExit(json.dumps(dict(error='references/index.json missing', refs=refs), ensure_ascii=False))
    return idx['files']


def resolve(key, refs=REFS):
    key = N(key.strip())
    files = index(refs)
    low = key.lower().replace('урок ', 'l').replace('практика ', 'p').replace('день ', 'd')
    for e in files:
        if key in (e['file'], e['id']) or low == e['id'].lower():
            return e
    m = re.match(r'^l?(\d)\.(\d+)$', low)
    if m:
        return next((e for e in files if e['id'] == 'L%s.%s' % m.groups()), None)
    m = re.match(r'^p0?(\d+)$', low)
    if m:
        return next((e for e in files if e['id'] == 'P%02d' % int(m.group(1))), None)
    m = re.match(r'^d0?(\d+)$', low)
    if m:
        return next((e for e in files if e['id'] == 'D%02d' % int(m.group(1))), None)
    return next((e for e in files if e['id'].lower() in ('pr-' + low, 'g-' + low) or e['title'] == key), None)


def lessons(refs=REFS):
    out = [e for e in index(refs) if e['kind'] == 'lesson' and re.match(r'^L\d\.\d+$', e['id'])]
    return sorted(out, key=lambda e: tuple(int(x) for x in e['id'][1:].split('.')))


def norm_words(text):
    text = N(text).lower().replace('ё', 'е')
    return re.findall(r'[0-9a-zа-я]+', text)


ENDINGS = sorted(['ями', 'ами', 'ого', 'его', 'ому', 'ему', 'ыми', 'ими', 'иях', 'ях', 'ах', 'ов', 'ев', 'ей', 'ий', 'ый',
                  'ой', 'ая', 'яя', 'ое', 'ее', 'ые', 'ие', 'ом', 'ем', 'ам', 'ям', 'ию', 'ья', 'ье', 'а', 'я', 'ы', 'и',
                  'у', 'ю', 'е', 'о', 'ь', 'й'], key=len, reverse=True)
STOP = {'что', 'как', 'какой', 'какая', 'какие', 'какую', 'сколько', 'мне', 'меня', 'это', 'для', 'при', 'надо', 'нужно',
        'можно', 'если', 'где', 'когда', 'или', 'так', 'уже', 'еще', 'есть', 'там', 'вот', 'про', 'по', 'на', 'не', 'же',
        'ли', 'бы', 'до', 'от', 'из', 'за', 'со', 'то', 'все', 'весь', 'курс', 'курсу', 'курса', 'метод', 'методу', 'ниф'}


def stem(w):
    """Strip one common Russian ending; stems are matched as word prefixes."""
    for e in ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[:-len(e)]
    return w


def find(query, limit=5, refs=REFS):
    q = sorted({stem(w) for w in norm_words(query) if (len(w) > 2 or w.isdigit()) and w not in STOP})
    if not q:
        return []
    res = []
    for e in index(refs):
        p = os.path.join(refs, e['file'])
        try:
            text = N(open(p, encoding='utf-8').read())
        except OSError:
            continue
        head = norm_words(e['title'] + ' ' + ' '.join(e.get('keywords') or []))
        # distinct query terms covered weigh most, then title/keywords, then lines matching several terms
        covered, line_score, lines = set(), 0, []
        score = 3 * sum(1 for s in q if any(w.startswith(s) for w in head))
        for line in text.splitlines():
            ws = norm_words(line)
            got = {s for s in q if any(w.startswith(s) for w in ws)}
            if got:
                covered |= got
                line_score += len(got) ** 2
                if line.strip() and not line.startswith(('---', 'keywords:', 'related:')):
                    lines.append((len(got), line.strip()[:220]))
        score = 2 * score + 4 * len(covered) + min(line_score, 20)
        if score:
            lines.sort(key=lambda x: -x[0])
            res.append(dict(file='references/' + e['file'], id=e['id'], title=e['title'], cite=e['cite'], score=score,
                            lines=[l for _, l in lines[:2]]))
    res.sort(key=lambda r: -r['score'])
    return res[:limit]


# ---------- calendar ----------

def d(s):
    return dt.date.fromisoformat(str(s)[:10])


def cycles(state):
    """Yield (sprint_start, sprint_in_quarter, audio, integration_days) from the configured sprint on."""
    start, q = d(state['sprint_start']), int(state.get('sprint_in_quarter') or 1)
    audio = bool(state.get('audio'))
    while True:
        integ = 14 if q == 3 else 7
        yield start, q, audio, integ
        start = start + dt.timedelta(days=SPRINT_DAYS + integ)
        q = q % 3 + 1
        audio = False


def position(day, state):
    first = d(state['sprint_start'])
    res = dict(date=day.isoformat(), weekday=WEEKDAY[day.weekday()])
    if first.weekday() != 0:
        res['warning'] = 'Спринт начат не в понедельник: аудио курса привязаны к дню недели (урок 0.2).'
    if day < first:
        res.update(period='before', days_until_sprint=(first - day).days, sprint_start=first.isoformat())
        return res
    for start, q, audio, integ in cycles(state):
        end = start + dt.timedelta(days=SPRINT_DAYS - 1)
        integ_end = end + dt.timedelta(days=integ)
        if day > integ_end:
            continue
        res.update(sprint_start=start.isoformat(), sprint_end=end.isoformat(), sprint_in_quarter=q,
                   integration_end=integ_end.isoformat(), course_sprint=audio)
        if day <= end:
            n = (day - start).days + 1
            res.update(period='sprint', sprint_day=n, sprint_week=(n - 1) // 7 + 1)
            if audio and n not in NO_AUDIO:
                res['audio_day'] = n
                res['audio_file'] = 'references/sprint/day-%02d.md' % n
            if n in REFLECTION_DAYS:
                res['weekly_reflection'] = True
        else:
            k = (day - end).days
            res.update(period='integration', integration_day=k, integration_week=(k - 1) // 7 + 1,
                       integration_days=integ, next_sprint_start=(integ_end + dt.timedelta(days=1)).isoformat())
        return res


def program_week(pos):
    if pos.get('period') == 'before':
        return None
    if not pos.get('course_sprint'):
        return None
    if pos['period'] == 'sprint':
        return pos['sprint_week'] + 2
    if pos['period'] == 'integration' and pos.get('integration_week') == 1:
        return 6
    return None


def run_where_cmd(cmd, day):
    try:
        argv = [os.path.expanduser(a) for a in shlex.split(cmd.replace('{date}', day.isoformat()))]
        p = subprocess.run(argv, capture_output=True, text=True, timeout=WHERE_CMD_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return None, '%s: %s' % (type(e).__name__, e)
    if p.returncode != 0:
        return None, 'exit %d: %s' % (p.returncode, (p.stderr or '').strip()[:300])
    try:
        return json.loads(p.stdout), None
    except ValueError:
        return None, 'not JSON: %s' % p.stdout.strip()[:300]


def where(day, data, profile, refs=REFS, override=None):
    state = load_json(os.path.join(data, 'state.json'), {})
    if override:
        state = dict(state, **override)
    out = dict(date=day.isoformat(), weekday=WEEKDAY[day.weekday()])
    done = set(state.get('lessons_done') or [])
    if state.get('sprint_start'):
        pos = position(day, state)
        out.update(pos)
        pw = program_week(pos)
        all_lessons = lessons(refs)
        if pw:
            out['program_week'] = pw
            out['lessons_this_week'] = [dict(id=e['id'], title=e['title'], file='references/' + e['file'], done=e['id'] in done)
                                        for e in all_lessons if str(e.get('week')) == str(pw)]
            out['overdue'] = [e['id'] for e in all_lessons if e['id'] not in done and e.get('week') not in (None, '')
                              and int(e['week']) < pw]
        nxt = next((e for e in all_lessons if e['id'] not in done), None)
        out['next_lesson'] = dict(id=nxt['id'], title=nxt['title'], file='references/' + nxt['file']) if nxt else None
        out['lessons_done'] = len(done)
    else:
        out['needs_setup'] = True
    if profile:
        out['profile'] = profile['path']
        if profile.get('error'):
            out['profile_error'] = profile['error']
        cmd = (profile.get('fields') or {}).get('where_cmd')
        if cmd:
            personal, err = run_where_cmd(cmd, day)
            if personal is not None:
                out['personal'] = personal
                out.pop('needs_setup', None)
            else:
                out['personal_error'] = err
    return out


# ---------- links (profile only) ----------

def kb_name(e):
    if e['kind'] == 'sprint-day':
        m = re.match(r'^День (\d+) спринта · (\S+)', e['title'])
        if m:
            return 'Аудио — День %s · %s' % m.groups()
    return e['title']


def link(keys, profile, refs=REFS):
    f = (profile or {}).get('fields') or {}
    vault, kb = f.get('vault'), f.get('kb_dir')
    if not vault or not kb:
        return dict(error='link needs a profile with vault and kb_dir')
    vault, kb = os.path.expanduser(vault), os.path.expanduser(kb)
    vault_name = f.get('vault_name') or os.path.basename(vault.rstrip('/'))
    notes = {}
    for dp, _, fn in os.walk(kb):
        for name in fn:
            if name.endswith('.md'):
                notes[N(name[:-3])] = N(os.path.relpath(os.path.join(dp, name), vault))
    out = []
    for k in keys:
        k = N(k.strip().strip('[]'))
        e = resolve(k, refs) if not k in notes else None
        name = kb_name(e) if e else k
        rel = notes.get(name)
        uri = None
        if rel:
            uri = 'obsidian://open?vault=%s&file=%s' % (urllib.parse.quote(vault_name),
                                                       urllib.parse.quote(rel[:-3] if rel.endswith('.md') else rel))
        out.append(dict(key=k, name=name, path=rel, uri=uri, exists=bool(rel)))
    return out


# ---------- progress, log, notes ----------

def lesson_id(s):
    s = N(s).strip().lower().replace('урок', '').replace('l', '').strip()
    m = re.match(r'^(\d)\.(\d+)$', s)
    return 'L%s.%s' % m.groups() if m else None


def progress(data, action, items, refs=REFS):
    sp = os.path.join(data, 'state.json')
    state = load_json(sp, {})
    done = list(state.get('lessons_done') or [])
    known = {e['id'] for e in lessons(refs)}
    bad = []
    for it in items:
        lid = lesson_id(it)
        if lid not in known:
            bad.append(it)
        elif action == 'mark' and lid not in done:
            done.append(lid)
        elif action == 'unmark' and lid in done:
            done.remove(lid)
    if action in ('mark', 'unmark'):
        state['lessons_done'] = sorted(done, key=lambda x: tuple(int(v) for v in x[1:].split('.')))
        save_json(sp, state)
    rows = [dict(id=e['id'], title=e['title'], week=e.get('week'), done=e['id'] in done) for e in lessons(refs)]
    return dict(done=len([r for r in rows if r['done']]), total=len(rows), unknown=bad,
                next=next((r for r in rows if not r['done']), None), lessons=rows if action == 'show' else None)


def now():
    return dt.datetime.now().replace(microsecond=0)


def log_add(data, zone, practice, note):
    os.makedirs(data, exist_ok=True)
    rec = dict(at=now().isoformat(), zone=zone, practice=practice, note=note)
    with open(os.path.join(data, 'log.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def log_show(data, days):
    since = (now() - dt.timedelta(days=days)).isoformat()
    out = []
    try:
        for line in open(os.path.join(data, 'log.jsonl'), encoding='utf-8'):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('at', '') >= since:
                out.append(r)
    except OSError:
        pass
    return out


def note_add(data, text):
    os.makedirs(data, exist_ok=True)
    line = '- %s · %s\n' % (now().date().isoformat(), text.strip())
    with open(os.path.join(data, 'notes.md'), 'a', encoding='utf-8') as f:
        f.write(line)
    return dict(added=line.strip())


# ---------- CLI ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default='')
    ap.add_argument('--profile', default='')
    ap.add_argument('--refs', default=REFS, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest='cmd', required=True)
    w = sub.add_parser('where'); w.add_argument('--date', default='')
    w.add_argument('--sprint-start', default='', help='use this sprint start once, without saving it')
    w.add_argument('--sprint-in-quarter', type=int, choices=(1, 2, 3), default=None)
    w.add_argument('--audio', choices=('yes', 'no'), default=None)
    s = sub.add_parser('setup'); s.add_argument('--sprint-start', required=True)
    s.add_argument('--sprint-in-quarter', type=int, choices=(1, 2, 3), default=1)
    s.add_argument('--audio', choices=('yes', 'no'), default='yes')
    p = sub.add_parser('progress'); p.add_argument('action', choices=('show', 'mark', 'unmark')); p.add_argument('items', nargs='*')
    f = sub.add_parser('find'); f.add_argument('query'); f.add_argument('--limit', type=int, default=5)
    sh = sub.add_parser('show'); sh.add_argument('key')
    li = sub.add_parser('link'); li.add_argument('keys', nargs='+')
    lg = sub.add_parser('log'); lg.add_argument('action', choices=('add', 'show'))
    lg.add_argument('--zone', default=''); lg.add_argument('--practice', default=''); lg.add_argument('--note', default='')
    lg.add_argument('--days', type=int, default=7)
    nt = sub.add_parser('note'); nt.add_argument('action', choices=('add', 'show')); nt.add_argument('text', nargs='*')
    sub.add_parser('state')
    a = ap.parse_args(argv)
    data, refs = data_dir(a.data), a.refs
    profile = load_profile(a.profile)
    out = None
    if a.cmd == 'where':
        day = d(a.date) if a.date else dt.date.today()
        override = None
        if a.sprint_start:
            override = dict(sprint_start=d(a.sprint_start).isoformat(), sprint_in_quarter=a.sprint_in_quarter or 1,
                            audio=a.audio != 'no')
        out = where(day, data, profile, refs, override)
    elif a.cmd == 'setup':
        start = d(a.sprint_start)
        sp = os.path.join(data, 'state.json')
        state = load_json(sp, {})
        state.update(sprint_start=start.isoformat(), sprint_in_quarter=a.sprint_in_quarter, audio=a.audio == 'yes')
        try:
            save_json(sp, state)
            out = dict(saved=sp, state=state)
        except OSError as e:
            out = dict(saved=None, state=state, error='state not saved (%s); pass --sprint-start to where instead' % e.strerror)
        if start.weekday() != 0:
            out['warning'] = 'Старт не в понедельник (%s). Курс просит начинать неделю спринта в понедельник (урок 0.2).' % WEEKDAY[start.weekday()]
    elif a.cmd == 'progress':
        out = progress(data, a.action, a.items, refs)
    elif a.cmd == 'find':
        out = find(a.query, a.limit, refs)
    elif a.cmd == 'show':
        e = resolve(a.key, refs)
        if not e:
            print(json.dumps(dict(error='not found', key=a.key), ensure_ascii=False))
            return 1
        sys.stdout.write(open(os.path.join(refs, e['file']), encoding='utf-8').read())
        return 0
    elif a.cmd == 'link':
        out = link(a.keys, profile, refs)
    elif a.cmd == 'log':
        out = log_add(data, a.zone, a.practice, a.note) if a.action == 'add' else log_show(data, a.days)
    elif a.cmd == 'note':
        if a.action == 'add':
            out = note_add(data, ' '.join(a.text))
        else:
            try:
                out = dict(notes=open(os.path.join(data, 'notes.md'), encoding='utf-8').read())
            except OSError:
                out = dict(notes='')
    elif a.cmd == 'state':
        out = dict(data=data, refs=refs, state=load_json(os.path.join(data, 'state.json'), {}),
                   profile=profile, log_entries=len(log_show(data, 36500)))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
