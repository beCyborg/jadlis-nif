---
# Every field is optional. Delete what you do not use.
emergency_number: "112"
# Your own calendar: a command that prints JSON for a date ({date} becomes YYYY-MM-DD).
# Runs without a shell, 15 s timeout; on failure the skill falls back to its own calendar.
where_cmd: ""
# Obsidian links: the vault root, its name, and the folder with your own notes on the course.
vault: ""
vault_name: ""
kb_dir: ""
---

# Мой профиль для /nif

The skill reads this file once per call and follows it on top of its own rules. A profile can change
rituals, links and where notes go. It cannot switch off the safety rules or the lesson references.

## Мои ритуалы

- Стендап — утром, до работы.
- Недельная рефлексия — в воскресенье вечером.

## Куда записывать

- Состояние и практику — в мой дневник: `~/notes/journal.md`, строкой «HH:MM · зона → практика».

## Мои решения по методу

- В оранжевой и синей зонах сначала тело, потом голова — это мой выбор, не правило курса.

## Если плохо

- Мой психотерапевт: имя и способ связи. Скилл предложит написать ему при долгой панике или апатии.
