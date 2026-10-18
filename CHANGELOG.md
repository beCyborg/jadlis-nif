# Changelog — jadlis-nif

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

## [1.0.0] — 2026-10-18 — Первый выпуск / First release

### Для человека

- Скилл `/jadlis-nif:nif` ведёт по методу нейроинтеграции Катерины Ленгольд в пяти режимах: где я и что дальше, вопрос по методу, острое состояние, разбор своего планирования, проекты спринта.
- Весь метод пересказан своими словами в 85 файлах: уроки, практики, дни спринта, протоколы, словари, карта программы, зоны шкалы, научные пометки. Материалы курса не нужны.
- Цитат курса нет. Скилл отказывается цитировать даже по просьбе.
- При тревожных симптомах тела скилл не даёт практик и направляет в экстренную службу.
- Личный профиль по желанию: свои ритуалы, ссылки, номер экстренной службы, свой календарь.
- Атлас метода с голосовым гидом: одна кнопка, 14 глав, от состояния к мышлению и действиям.

### For agents

- Added: `skills/nif/SKILL.md` — five modes, Step 0 `nif.py where` with `${CLAUDE_PLUGIN_DATA}` and `${user_config.PROFILE_PATH}`, routing table (≤3 files per answer), safety section above every mode, fallback to direct Read when the script cannot run.
- Added: `skills/nif/scripts/nif.py` (stdlib, Python 3.9+) — `where`, `setup`, `progress`, `find`, `show`, `link`, `log`, `note`, `state`; sprint of 21 days, audio days 1–20 except 7 and 14, reflection days 6/13/20, integration 7 days or 14 after the third sprint of a quarter; profile `where_cmd` without a shell, 15 s timeout.
- Added: `skills/nif/references/` (85 files + `index.json`), `tools/build_index.py`, `tools/check_refs.py` (banned personal markers, source-place markers, quotes over 6 words, broken links, index sync).
- Added: `userConfig.PROFILE_PATH` (string, optional).
- Added: `evals/` — 20 cases for `claude plugin eval`; `tests/test_nif_cli.py`.
- Added: `docs/atlas/` — `atlas.src.html`, `build_atlas.py` (`--share` / `--personal`; `<!--@move-->` / `<!--@put-->` reorder the public build), `narration.json`, `tts_gen.py`.
