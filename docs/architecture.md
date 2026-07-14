# Cleva Regulatory Library v0.2 Architecture

```text
User query
   |
   +-- Quick search: curated official + professional sources
   +-- Official search: government / regulator / legal databases only
   +-- Deep search: expanded keywords + curated domains + broad web discovery
   |
Search provider / official API
   |
Fetch HTML or PDF
   |
DeepSeek / OpenAI preliminary extraction
   |
Human review queue
   |-----------------------------|
   |                             |
Formal Regulation Library       Regulatory Intelligence Library
(official link required)        (commentary, alerts, PRO notices, media)
   |                             |
Excel / Word export             Excel export
```

## Trust model

- Level A: official legislation and legal databases.
- Level B: regulator guidance, official notification platforms, authorised or operational organisations.
- Level C: testing, certification and regulatory consulting organisations.
- Level D: industry media, company commentary and market intelligence.

Professional sources can discover and explain regulations, but cannot replace the official legal text.
