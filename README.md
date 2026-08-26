# Юрист Мегаполиса

Агент (не веб-приложение) — руководитель юридической службы: советник 24/7 по сделкам с
недвижимостью, долям, налогам, личным юридическим вопросам владелицы, и сборщик комплекта
`.docx`-документов. Работает как диалог в Claude Code, открытый прямо в этой папке
(`CLAUDE.md` — точка входа).

## С чего начать

Открой `HOME.md`.

## Структура

```
CLAUDE.md            — точка входа для Claude Code
HOME.md, SOUL.md, ROUTING.md, PROFILE.md, DECISIONS.md, MEMORY.md, OPEN_QUESTIONS.md
knowledge/
  deal-schema.md          — модель данных Deal/Participant, правила комплекта
  precedents.md            — реестр прецедентов (пополняется по подтверждению владельца)
  found_materials/         — личные документы клиентов, в git не отслеживаются
skills/
  document-assembly/       — движок сборки .docx (scripts/ + templates_docx/ + document_rules.json)
  legal-research/           — поиск норм права и судебной практики
telegram_bot/               — канал агент↔Telegram (постоянный процесс, запускается отдельно)
deals/<deal_id>/deal.json   — данные текущих сделок
output/<deal_id>/*.docx     — готовые документы
examples/                    — образец сделки и стиля диалога
ЛИЧНОЕ/                       — личные юридические вопросы владелицы, отдельно от бизнеса
product-saas-prototype/       — более ранняя веб-версия, справочный материал, не рабочий путь
```
