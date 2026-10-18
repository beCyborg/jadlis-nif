import datetime as dt, importlib.util, json, os, stat, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('nif_cli', os.path.join(HERE, '..', 'skills', 'nif', 'scripts', 'nif.py'))
nif = importlib.util.module_from_spec(spec); spec.loader.exec_module(nif)

LESSONS = [('L0.1', 0), ('L1.4', 1), ('L2.6', 2), ('L3.1', 3), ('L3.2', 3), ('L4.1', 4), ('L5.2', 5), ('L6.1', 6)]


def refs_fixture():
    r = tempfile.mkdtemp()
    files = []
    for lid, week in LESSONS:
        rel = 'lessons/l%s.md' % lid[1:].replace('.', '-')
        files.append(dict(file=rel, id=lid, title='Урок %s — тема' % lid[1:], kind='lesson', cite='урок ' + lid[1:], week=week))
    files.append(dict(file='sprint/day-03.md', id='D03', title='День 3 спринта · среда', kind='sprint-day', cite='аудио дня 3', week=1))
    files.append(dict(file='practices/p02.md', id='P02', title='Практика 02 — Базовое дыхание со счётом', kind='practice',
                      cite='практика 2', keywords=['дыхание', 'длинный выдох', 'стресс']))
    files.append(dict(file='protocols/sane.md', id='PR-sane', title='Протокол — SANE (острое состояние)', kind='protocol', cite='протокол SANE'))
    for e in files:
        p = os.path.join(r, e['file'])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        body = '# %s\n\nТекст.\n' % e['title']
        if e['id'] == 'P02':
            body += '\n## Шаги\n1. Вдох на 4 счёта, выдох длиннее вдоха.\n'
        if e['id'] == 'L1.4':
            body += '\n## Правила и числа\n- Спринт — 3 недели, 3 проекта, 30 часов.\n'
        open(p, 'w', encoding='utf-8').write('---\nid: %s\n---\n%s' % (e['id'], body))
    json.dump(dict(files=files), open(os.path.join(r, 'index.json'), 'w'), ensure_ascii=False)
    return r


REFS = refs_fixture()


def setup_state(start='2026-11-09', q=2, audio='yes'):
    data = tempfile.mkdtemp()
    nif.main(['--data', data, '--refs', REFS, 'setup', '--sprint-start', start, '--sprint-in-quarter', str(q), '--audio', audio])
    return data


def where(data, date, profile=None):
    return nif.where(dt.date.fromisoformat(date), data, profile, REFS)


def test_where_plan_dates():
    data = setup_state()
    r = where(data, '2026-10-25')
    assert r['period'] == 'before' and r['days_until_sprint'] == 15 and r['next_lesson']['id'] == 'L0.1'
    r = where(data, '2026-11-11')
    assert (r['period'], r['sprint_day'], r['sprint_week'], r['audio_day']) == ('sprint', 3, 1, 3)
    assert r['audio_file'] == 'references/sprint/day-03.md' and r['program_week'] == 3
    assert [x['id'] for x in r['lessons_this_week']] == ['L3.1', 'L3.2'] and 'L1.4' in r['overdue']
    r = where(data, '2026-11-14')
    assert r['sprint_day'] == 6 and r['audio_day'] == 6 and r['weekly_reflection']
    r = where(data, '2026-11-15')
    assert r['sprint_day'] == 7 and 'audio_day' not in r and r['weekday'] == 'воскресенье'
    r = where(data, '2026-11-28')
    assert r['sprint_day'] == 20 and r['audio_day'] == 20 and r['weekly_reflection'] and r['program_week'] == 5
    r = where(data, '2026-11-30')
    assert (r['period'], r['integration_day'], r['integration_days'], r['program_week']) == ('integration', 1, 7, 6)
    assert r['next_sprint_start'] == '2026-12-07'
    r = where(data, '2026-12-07')
    assert (r['period'], r['sprint_day'], r['sprint_in_quarter'], r['course_sprint']) == ('sprint', 1, 3, False)
    assert 'audio_day' not in r and 'program_week' not in r


def test_quarter_end_has_two_integration_weeks():
    data = setup_state(q=3)
    r = where(data, '2026-12-07')
    assert r['period'] == 'integration' and r['integration_days'] == 14 and r['integration_week'] == 2
    assert where(data, '2026-12-14')['period'] == 'sprint'


def test_non_monday_start_warns():
    data = tempfile.mkdtemp()
    out = []
    old = sys.stdout
    try:
        sys.stdout = type('W', (), {'write': lambda s, x: out.append(x), 'flush': lambda s: None})()
        nif.main(['--data', data, '--refs', REFS, 'setup', '--sprint-start', '2026-11-11'])
    finally:
        sys.stdout = old
    assert 'не в понедельник' in ''.join(out)
    assert 'warning' in where(data, '2026-11-12')


def test_no_state_needs_setup():
    r = where(tempfile.mkdtemp(), '2026-11-11')
    assert r['needs_setup'] and 'period' not in r


def test_data_dir_fallbacks(monkeypatch):
    monkeypatch.setenv('CLAUDE_PLUGIN_DATA', '/tmp/x-data')
    assert nif.data_dir('${CLAUDE_PLUGIN_DATA}') == '/tmp/x-data'
    assert nif.data_dir('/given') == '/given'
    monkeypatch.delenv('CLAUDE_PLUGIN_DATA')
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', '/cfg')
    assert nif.data_dir('') == '/cfg/plugins/data/jadlis-nif-jadlis'


def profile_with(cmd, extra=''):
    p = os.path.join(tempfile.mkdtemp(), 'nif-profile.md')
    open(p, 'w', encoding='utf-8').write('---\nwhere_cmd: "%s"\n%s---\n# Профиль\n' % (cmd, extra))
    return nif.load_profile(p)


def script(body):
    p = os.path.join(tempfile.mkdtemp(), 'cal.py')
    open(p, 'w').write('import sys, json, time\n' + body)
    return p


def test_where_cmd_attaches_personal_and_skips_setup():
    s = script('print(json.dumps({"date": sys.argv[1], "audio_day": 3}))')
    r = where(tempfile.mkdtemp(), '2026-11-11', profile_with('%s %s {date}' % (sys.executable, s)))
    assert r['personal'] == {'date': '2026-11-11', 'audio_day': 3} and 'needs_setup' not in r


def test_where_cmd_failure_keeps_answer():
    data = setup_state()
    s = script('sys.exit(3)')
    r = where(data, '2026-11-11', profile_with('%s %s' % (sys.executable, s)))
    assert r['sprint_day'] == 3 and r['personal_error'].startswith('exit 3')
    r = where(data, '2026-11-11', profile_with('/no/such/binary'))
    assert 'personal_error' in r and r['sprint_day'] == 3


def test_where_cmd_timeout(monkeypatch):
    monkeypatch.setattr(nif, 'WHERE_CMD_TIMEOUT', 1)
    s = script('time.sleep(5)')
    r = where(setup_state(), '2026-11-11', profile_with('%s %s' % (sys.executable, s)))
    assert r['personal_error'].startswith('TimeoutExpired')


def test_where_cmd_has_no_shell():
    flag = os.path.join(tempfile.mkdtemp(), 'pwned')
    r = where(setup_state(), '2026-11-11', profile_with('echo ok; touch %s' % flag))
    assert not os.path.exists(flag) and 'personal_error' in r


def test_progress_mark_unmark():
    data = setup_state()
    r = nif.progress(data, 'mark', ['1.4', 'урок 0.1', 'L9.9'], REFS)
    assert r['done'] == 2 and r['unknown'] == ['L9.9'] and r['next']['id'] == 'L2.6'
    r = nif.progress(data, 'unmark', ['0.1'], REFS)
    assert r['done'] == 1 and r['next']['id'] == 'L0.1'
    assert where(data, '2026-11-11')['lessons_done'] == 1


def test_find_and_resolve():
    r = nif.find('дыхание на выдохе при стрессе', refs=REFS)
    assert r[0]['id'] == 'P02' and r[0]['file'] == 'references/practices/p02.md'
    assert nif.find('сколько часов на спринт', refs=REFS)[0]['id'] == 'L1.4'
    assert nif.resolve('1.4', REFS)['id'] == 'L1.4'
    assert nif.resolve('p2', REFS)['id'] == 'P02'
    assert nif.resolve('D3', REFS)['id'] == 'D03'
    assert nif.resolve('sane', REFS)['id'] == 'PR-sane'


def test_log_and_note():
    data = tempfile.mkdtemp()
    nif.log_add(data, 'оранжевая', 'p02', '')
    assert nif.log_show(data, 1)[0]['zone'] == 'оранжевая'
    assert nif.note_add(data, 'вывод')['added'].endswith('· вывод')


def test_link_needs_profile_vault():
    assert 'error' in nif.link(['L1.4'], None, REFS)
    vault = tempfile.mkdtemp()
    kb = os.path.join(vault, 'База')
    os.makedirs(kb)
    open(os.path.join(kb, 'Аудио — День 3 · среда.md'), 'w').write('x')
    prof = profile_with('x', 'vault: "%s"\nkb_dir: "%s"\nvault_name: "V"\n' % (vault, kb))
    r = nif.link(['D03', 'Нет такой'], prof, REFS)
    assert r[0]['exists'] and r[0]['uri'].startswith('obsidian://open?vault=V&file=') and not r[1]['exists']


def test_where_one_off_sprint_start_without_state():
    data = tempfile.mkdtemp()
    r = nif.where(dt.date(2026, 11, 11), data, None, REFS, dict(sprint_start='2026-11-09', sprint_in_quarter=1, audio=True))
    assert r['sprint_day'] == 3 and r['audio_day'] == 3 and not os.path.exists(os.path.join(data, 'state.json'))
