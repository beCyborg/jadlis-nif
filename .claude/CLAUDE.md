# jadlis-nif — notes for agents working on this repo

- Root = the plugin. One skill: `skills/nif/` (SKILL.md, `scripts/nif.py`, `references/`).
- `references/` is a retelling of a paid course in the owner's own words. Never add quotes, transcripts, slide text or audio. After any edit: `python3 tools/build_index.py`, then `python3 tools/check_refs.py`. The owner also runs a private verbatim gate against the course materials before every release; it is not part of this repo.
- `nif.py` stays stdlib-only and Python 3.9 compatible. `${CLAUDE_PLUGIN_DATA}` and `${user_config.*}` are substituted in SKILL.md only, never in the Bash environment: pass them as arguments.
- Tests: `uv run --with pytest pytest tests/ -q`. Evals: `claude plugin eval . --trust-plugin --runs 1 --ablation none --allow-tools "Bash(python3:*)"`; results go to `evals/results/` (ignored).
- Atlas: edit `docs/atlas/atlas.src.html`; build with `python3 docs/atlas/build_atlas.py --share --out docs/atlas/build/share`. The personal layer is a private JSON passed with `--personal`; it never enters this repo. Lint the share build with `python3 tools/check_refs.py --files <index.html> --allow 'jadlis-(nif|hub)' --allow '@jadlis\b' --quote-words 12`.
- Release: bump `version` in `.claude-plugin/plugin.json`, CHANGELOG entry, commit, `claude plugin tag . --push`, then pin the tag in the jadlis-hub catalogue.
