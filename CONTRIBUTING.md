Русский · [English](#english)

# Как предложить правку

Репозиторий публичный, пишет в него только владелец. Правки — через **форк + merge request**.

1. Форк и ветка от `main`.
2. Перед коммитом: `python3 tools/check_refs.py`, `python3 tools/build_index.py --check`, тесты (`TESTS.md`), `claude plugin validate . --strict`, `gitleaks git .`; README — по контракту (RU + EN, одинаковые H2, без Mermaid).
3. Правка пересказа — только своими словами. Цитаты, расшифровки, слайды и аудио курса в репозиторий не попадают.
4. Одна тема — один MR. В описании — что меняется для получателя.
5. Ключи, почты, личные пути в репо не попадают.

Релизы и теги (`jadlis-nif--vX.Y.Z`) делает владелец. Тексты и код написаны вместе с Claude Code; за содержание отвечает владелец.

---

## English

Public repository, owner-only writes. Contributions via **fork + merge request**: branch from `main`, run `python3 tools/check_refs.py`, `python3 tools/build_index.py --check`, the tests in `TESTS.md`, `claude plugin validate . --strict` and `gitleaks git .`, keep README RU/EN in sync (same H2 set, no Mermaid), one topic per MR, no keys or personal paths. Edits to the retelling stay in your own words: no quotes, transcripts, slides or audio of the course.

Releases and tags (`jadlis-nif--vX.Y.Z`) are cut by the owner. Text and code are written together with Claude Code; the owner is accountable for the content.
