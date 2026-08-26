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

## Как завести новый тип документа (handoff §13.2) — без правки кода

Раньше состав комплекта был зашит в Python (`rules.py`). Теперь он читается из
`document_rules.json` — это данные, не код, агент правит сам. Три шага:

1. Добавить `.docx`-шаблон с Jinja-плейсхолдерами в `templates_docx/` + запись в
   `templates_docx/registry.json` (новый `document_type`, статус `active`).
2. Добавить правило в `document_rules.json` — когда этот документ нужен:
   - `per_participant` — по одному на каждого участника;
   - `once_per_deal` — один на сделку, если есть хоть один участник;
   - `per_participant_flag` — по одному на участника с выставленным флагом
     (флаг ищется сначала как поле `Participant`, потом в `Participant.extra_flags`
     — новый триггер согласия можно завести через `extra_flags`, тоже без правки кода).
3. Проверить `check_completeness.py` на тестовой сделке — новый документ должен появиться
   в списке.

Если нужного вида правила нет среди трёх (например, «один документ на каждую сторону»,
а не на каждого участника) — это уже задача инженеру, `rules.py` учит новый `scope`.

## Формат данных

`deal.json` (см. `knowledge/deal-schema.md` за полной схемой) — единственный источник
истины для рендеринга одной сделки. Хранится в `deals/<deal_id>/deal.json`.
