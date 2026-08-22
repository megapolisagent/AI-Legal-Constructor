---
name: document-assembly
description: Собрать комплект .docx договоров сделки (аренда/продажа недвижимости) из deal.json — используй, когда данные сделки и участников собраны и нужно проверить полноту/сгенерировать документы.
---

# Document Assembly — сборка комплекта договоров

Движок перенесён без изменения логики из веб-прототипа (`archive/web_proto/app/`,
2026-08-21) — структура данных и правила комплекта не менялись, менялся только способ
ввода (диалог вместо веб-формы) и то, что это теперь Skill внутри Foundation-агента,
не отдельное Flask-приложение.

## Схема данных и правила комплекта

`../../knowledge/deal-schema.md` — Deal/Participant, обязательные поля, правила состава
комплекта (сколько комиссий, когда нужен акт/согласие). Читай перед сбором данных сделки,
не держи в контексте на каждое сообщение.

## Инструменты

Запускать из корня репозитория (`AI Legal Constructor/`):

```bash
python skills/document-assembly/scripts/check_completeness.py deals/<deal_id>/deal.json
python skills/document-assembly/scripts/generate_package.py deals/<deal_id>/deal.json
python skills/document-assembly/scripts/registry_lookup.py <document_type> <deal_type>
```

- `check_completeness.py` — печатает итоговый список документов и (если есть) незаполненные
  поля. Не генерирует файлы.
- `generate_package.py` — рендерит комплект в `output/<deal_id>/`. Отказывает, если есть
  незаполненные поля (сначала `check_completeness.py`).
- `registry_lookup.py` — найти активный шаблон для пары (document_type, deal_type),
  диагностика при ошибке `TemplateNotFound`.

## Шаблоны

`templates_docx/registry.json` + `*.docx` — реестр с правилом «один `active`-шаблон на
пару document_type×deal_type» (§5 handoff). Текущие `.docx` — **тестовые заглушки**, не
юридический текст (см. пометку внутри каждого файла) — реальный текст готовят Мария/юрист
отдельно, движок примет реальные шаблоны с той же Jinja-разметкой без изменения кода.

## Формат данных

`deal.json` (см. `knowledge/deal-schema.md` за полной схемой) — единственный источник
истины для рендеринга одной сделки. Хранится в `deals/<deal_id>/deal.json`.
