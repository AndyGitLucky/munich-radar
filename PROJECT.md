# München Radar

## 1. Project Goal

Build a lightweight web application that automatically collects relevant events, activities, exhibitions, festivals, public happenings, and useful city information for Munich and presents only the most relevant items in a compact daily overview.

The product should answer questions like:

- What is worth knowing about in Munich today?
- What is happening tomorrow?
- What interesting things are happening this weekend?
- Which exhibitions, festivals, or seasonal events have recently started?
- What important events are coming up soon?
- Is there anything unusual or particularly relevant that I might otherwise miss?

The application should not become another huge generic event database.

The core value is:

> Reduce thousands of possible Munich events to a small, useful, curated daily selection.

Working title:

**München Radar**

---

# 2. MVP Philosophy

Keep the first version simple.

Do NOT build:

- a mobile app
- user accounts
- authentication
- a complex backend
- a vector database
- a multi-agent architecture
- a permanent server
- a recommendation ML system
- an autonomous web browsing agent

The MVP should be able to run almost entirely using:

- Python
- GitHub Actions
- JSON
- HTML/CSS/JavaScript
- GitHub Pages

The system should periodically collect data, normalize it, calculate relevance, and generate a static website.

---

# 3. Deployment Target

The project should initially be deployable for free using:

- GitHub repository
- GitHub Actions
- GitHub Pages

Architecture:

```text
Event Sources
     ↓
Python collectors
     ↓
Normalization
     ↓
Deduplication
     ↓
Filtering
     ↓
Relevance scoring
     ↓
data/events.json
     ↓
Static web frontend
     ↓
GitHub Pages
```

The data update process should run automatically through GitHub Actions.

Recommended frequency:

```text
2–4 times per day
```

For example:

```text
06:00
11:00
16:00
21:00
```

The exact schedule should remain easy to change.

---

# 4. Primary User Experience

The landing page should immediately show a useful overview.

Suggested navigation:

```text
Heute
Morgen
Wochenende
Demnächst
Neu
```

The default page should be:

```text
Heute
```

Example:

```text
MÜNCHEN RADAR

Sonntag, 13. September

🔥 Heute relevant

Corso Leopold
Straßenfestival
11:00–21:00
Leopoldstraße
Kostenlos

Warum interessant:
Großes Straßenfest, nur dieses Wochenende.


🧪 Neu entdeckt

Neue Ausstellung im Deutschen Museum

Warum interessant:
Neue Dauerausstellung, Technik/Wissenschaft.


📅 Heads-up

Oktoberfest beginnt nächste Woche.
```

The application should prefer showing 5 useful entries instead of 50 mediocre entries.

---

# 5. Event Categories

Initial supported categories:

```text
festival
street_festival
museum
exhibition
science
technology
family
children
market
flea_market
culture
concert
theatre
food
seasonal
outdoor
city_event
public_event
other
```

Later possible categories:

```text
traffic
construction
public_transport
demonstration
weather_related
city_policy
sports
meetup
conference
ai
robotics
maker
```

---

# 6. Data Sources

Collectors should be modular.

Each source should have its own collector implementation.

Potential sources include:

```text
muenchen.de
Deutsches Museum
Münchner Stadtmuseum
Pinakotheken
Lenbachhaus
Haus der Kunst
Münchner Stadtbibliothek
Gasteig
Olympiapark
Tollwood
Messe München
MVV/MVG event-related information
official district / Bezirksausschuss pages
selected Meetup/event pages
```

Do not implement every source immediately.

Start with approximately 3–5 reliable sources.

Priority:

1. official sources
2. structured sources
3. sources with stable URLs
4. sources with clear dates and locations

Avoid fragile scraping if a structured page, feed, JSON endpoint, calendar export, or API exists.

---

# 7. Collector Interface

Collectors should follow a common interface.

Example:

```python
class EventCollector:
    def collect(self) -> list[RawEvent]:
        ...
```

Each collector should only be responsible for retrieving and parsing its own source.

Collectors must NOT contain relevance logic.

Example directory:

```text
src/
    collectors/
        base.py
        muenchen_de.py
        deutsches_museum.py
        stadtbibliothek.py
```

---

# 8. Normalized Event Model

All events must be converted into one common schema.

Suggested model:

```python
Event:
    id: str

    title: str
    description: str | None

    start: datetime | None
    end: datetime | None

    location_name: str | None
    address: str | None
    district: str | None

    category: str
    tags: list[str]

    price_text: str | None
    is_free: bool | None

    family_friendly: bool | None

    source_name: str
    source_url: str

    image_url: str | None

    discovered_at: datetime
    updated_at: datetime

    relevance_score: float | None
    relevance_reasons: list[str]
```

Store timestamps using ISO 8601.

Example:

```json
{
  "start": "2026-09-13T11:00:00+02:00"
}
```

Timezone:

```text
Europe/Berlin
```

---

# 9. Event IDs

Event IDs must remain stable between updates whenever possible.

Do not generate a new random UUID during every crawl.

Preferred strategy:

Create a deterministic hash from fields such as:

```text
normalized title
start date
location
source
```

Example:

```python
sha256(
    title_normalized +
    start_date +
    location_normalized +
    source_name
)
```

---

# 10. Deduplication

The same event may appear on several websites.

Deduplication is therefore required.

Initial heuristic:

Compare:

```text
title similarity
start date
location
```

Possible matching rule:

```text
same date
AND
similar title
AND
same or similar location
```

Do not delete alternate sources.

Instead merge them.

Example:

```json
"sources": [
    {
        "name": "muenchen.de",
        "url": "..."
    },
    {
        "name": "Deutsches Museum",
        "url": "..."
    }
]
```

Prefer an official organizer source as the primary source.

---

# 11. Relevance System

The core feature is relevance ranking.

Do NOT initially use machine learning.

Use an explainable scoring system.

Example:

```text
score =
    event_importance
  + personal_interest
  + novelty
  + timing
  + rarity
  + family_value
  + free_bonus
  + seasonal_relevance
```

Possible score range:

```text
0–100
```

---

# 12. Example Relevance Rules

Examples:

```text
major Munich festival                  +25
new museum exhibition                  +20
science / technology                   +15
family friendly                        +10
free event                              +5
only happening today                  +10
only happening this weekend           +10
large seasonal event                  +15
recurring weekly generic event        -10
generic commercial event              -10
duplicate event                       -50
```

Keep these values configurable.

Example:

```text
config/relevance.yaml
```

---

# 13. Personal Preferences

Initial preferences may be stored in a configuration file.

Example:

```yaml
interests:
  science: 1.0
  technology: 1.0
  museum: 0.8
  exhibition: 0.8
  family: 0.8
  street_festival: 0.8
  market: 0.5
  concert: 0.3
```

Avoid hardcoding personal preferences directly into application logic.

---

# 14. Explainability

Every recommended event should include short reasons.

Example:

```json
"relevance_reasons": [
    "Neue Ausstellung",
    "Technik/Wissenschaft",
    "Nur dieses Wochenende",
    "Kostenlos"
]
```

The UI should display something similar to:

```text
Warum interessant:
Neue Ausstellung · Technik · Kostenlos
```

This is an important product feature.

---

# 15. Time-Based Views

The system should automatically classify events.

## Heute

Events occurring today.

## Morgen

Events occurring tomorrow.

## Wochenende

Events happening on the upcoming Saturday or Sunday.

If today is already Saturday or Sunday, use the current weekend.

## Demnächst

Relevant events within approximately:

```text
next 30 days
```

## Neu

Events that were newly discovered recently.

Example:

```text
discovered within last 72 hours
```

---

# 16. Heads-Up System

Some events should appear before they happen.

Example:

```text
Oktoberfest begins in 6 days
New exhibition starts tomorrow
Large city festival next weekend
```

Possible trigger thresholds:

```text
major event:
14 days
7 days
3 days
1 day
```

Smaller event:

```text
3 days
1 day
```

---

# 17. Website

The website should be mobile-friendly and simple.

Avoid heavy frontend frameworks unless clearly justified.

Preferred MVP:

```text
HTML
CSS
vanilla JavaScript
```

React/Next.js should NOT be introduced unless the project actually needs it.

Primary goal:

```text
fast
simple
readable
maintainable
```

---

# 18. UI Structure

Suggested card:

```text
┌─────────────────────────────┐
│ Corso Leopold               │
│ Street Festival             │
│                             │
│ Today · 11:00–21:00         │
│ Leopoldstraße               │
│ Free                        │
│                             │
│ Why interesting             │
│ Only this weekend           │
│ Major Munich event          │
│                             │
│ More info →                 │
└─────────────────────────────┘
```

Cards should contain only essential information.

---

# 19. Visual Priority

Recommended events may have simple priority indicators.

Example:

```text
🔥 Highly relevant
⭐ Recommended
👀 Interesting
📅 Heads-up
🆕 New
```

Avoid excessive icons or visual clutter.

---

# 20. Repository Structure

Suggested structure:

```text
munich-radar/
│
├── PROJECT.md
├── README.md
├── requirements.txt
├── pyproject.toml
│
├── config/
│   ├── sources.yaml
│   └── relevance.yaml
│
├── src/
│   ├── collectors/
│   │   ├── base.py
│   │   ├── muenchen_de.py
│   │   └── deutsches_museum.py
│   │
│   ├── models/
│   │   └── event.py
│   │
│   ├── normalize.py
│   ├── deduplicate.py
│   ├── scoring.py
│   ├── pipeline.py
│   └── main.py
│
├── data/
│   ├── events.json
│   └── metadata.json
│
├── web/
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── tests/
│   ├── test_normalize.py
│   ├── test_deduplicate.py
│   └── test_scoring.py
│
└── .github/
    └── workflows/
        └── update-events.yml
```

---

# 21. Pipeline

The pipeline should be deterministic and callable locally.

Command:

```bash
python -m src.main
```

Pipeline:

```text
load configuration

↓
run collectors

↓
store raw results

↓
normalize

↓
validate

↓
deduplicate

↓
score

↓
sort

↓
write events.json

↓
write metadata.json
```

One failing collector must not crash the entire update.

Example behavior:

```text
3 collectors successful
1 collector failed

Pipeline continues.
Error is logged.
```

---

# 22. Metadata

Generate:

```text
data/metadata.json
```

Example:

```json
{
  "last_updated": "2026-09-13T06:00:00+02:00",
  "sources_checked": 5,
  "sources_successful": 4,
  "events_collected": 342,
  "events_after_deduplication": 274
}
```

The frontend should show:

```text
Last updated: 06:02
```

---

# 23. Logging

Use Python `logging`.

Do not use random print statements for normal application logging.

Log:

```text
collector start
collector success
number of events
collector failure
deduplication statistics
output statistics
```

Do not log secrets.

---

# 24. Error Handling

Network errors are expected.

Collectors should handle:

```text
timeouts
HTTP errors
unexpected HTML changes
empty responses
invalid dates
missing fields
```

One malformed event should not break an entire collector.

---

# 25. HTTP Rules

Use a clear user agent.

Example:

```text
MunichRadar/0.1
```

Use reasonable timeouts.

Example:

```text
10–20 seconds
```

Do not aggressively crawl websites.

Respect:

```text
robots.txt
rate limits
terms of service
```

Prefer official APIs or structured endpoints when available.

---

# 26. Caching

Avoid repeatedly downloading unchanged resources.

Possible future implementation:

```text
ETag
Last-Modified
local HTTP cache
```

Not required for the first implementation.

---

# 27. Optional LLM Integration

LLM usage is NOT required for the basic MVP.

The deterministic system must work without an LLM.

Possible later LLM tasks:

```text
summarize descriptions
generate category tags
estimate event relevance
generate short relevance explanations
merge duplicate descriptions
identify unusual events
```

LLM output must never overwrite known factual data such as:

```text
date
time
price
location
event URL
```

Those fields must come from source data.

---

# 28. API Keys

Never expose API keys in frontend JavaScript.

Secrets must be stored using:

```text
GitHub Actions Secrets
```

Example:

```text
OPENROUTER_API_KEY
```

The static frontend must never contain secrets.

---

# 29. GitHub Actions

Create a workflow that:

```text
checks out repository
installs Python
installs dependencies
runs pipeline
updates generated JSON
commits changed data
deploys GitHub Pages
```

The workflow should also support manual execution:

```yaml
workflow_dispatch:
```

A failed source should not necessarily fail the entire workflow.

A fatal pipeline error should.

---

# 30. Testing

Important core logic should have tests.

Minimum:

```text
date normalization
event normalization
stable event IDs
deduplication
relevance scoring
time classification
```

Collectors may use saved HTML fixtures for parser tests.

Do not perform live web requests in unit tests.

---

# 31. Data Validation

Before writing an event to the final dataset validate:

```text
title exists
source exists
source URL exists
date format valid if present
category valid
```

Invalid events should be skipped and logged.

---

# 32. Security

Do not execute content retrieved from external websites.

Treat scraped content as untrusted input.

Escape user-visible HTML.

Never use:

```python
eval()
exec()
```

on external content.

---

# 33. Performance

The expected dataset is small.

Optimization is not a priority.

Prefer readable implementations over premature optimization.

Expected scale:

```text
hundreds or a few thousand events
```

SQLite may be introduced later if necessary.

For MVP:

```text
JSON is sufficient.
```

---

# 34. Definition of MVP

Version `0.1` is complete when:

- at least 3 real Munich sources are integrated
- events are collected automatically
- events use one normalized schema
- duplicates are reduced
- relevance scoring exists
- `Heute`, `Morgen`, `Wochenende`, and `Demnächst` work
- generated data is stored as JSON
- a static website displays the events
- GitHub Actions can update the data automatically
- GitHub Pages can host the result
- the site is usable on desktop and mobile

---

# 35. Non-Goals for v0.1

Do not implement yet:

```text
user accounts
mobile app
push notifications
native notifications
social features
comments
payments
complex AI agents
vector databases
user tracking
analytics platform
multi-city support
```

---

# 36. Future Ideas

Possible future capabilities:

## Personalization

Users can select interests:

```text
family
technology
culture
food
nightlife
outdoor
science
music
```

## Feedback

Simple buttons:

```text
👍 interesting
👎 not interested
```

This can adjust future scoring.

## Calendar Export

Allow:

```text
Add to calendar
ICS export
Google Calendar
Apple Calendar
```

## Notifications

Example:

```text
3 things worth knowing about in Munich today
```

Possible channels:

```text
browser notification
email
Telegram
Signal
mobile app
```

## Geographic Filtering

Example:

```text
within 3 km
within 10 km
Munich only
```

## Weather Awareness

Example:

```text
Outdoor festival + heavy rain forecast

→ lower recommendation
```

## City Intelligence

Expand beyond events:

```text
major construction
public transport disruptions
road closures
public demonstrations
temporary park closures
seasonal openings
public swimming information
city services
```

This could eventually transform the project from an event calendar into a true:

> Munich daily situational awareness system.

---

# 37. Coding Guidelines

Use:

```text
Python 3.12+
type hints
dataclasses or Pydantic where useful
small modules
clear function boundaries
explicit error handling
```

Prefer:

```python
def normalize_event(raw: RawEvent) -> Event:
    ...
```

over large procedural scripts.

Functions should generally perform one clear task.

Avoid unnecessary abstractions.

---

# 38. Dependency Policy

Keep dependencies minimal.

Likely useful:

```text
requests or httpx
beautifulsoup4
python-dateutil
PyYAML
rapidfuzz
```

Optional:

```text
pydantic
```

Do not introduce frameworks without a clear reason.

---

# 39. Codex Working Instructions

When implementing this project:

1. Read `PROJECT.md` completely before making architectural changes.
2. Prefer the simplest implementation that satisfies the requirement.
3. Do not introduce major frameworks without justification.
4. Preserve modular collectors.
5. Keep scraped source logic isolated from application logic.
6. Never expose secrets.
7. Add tests when implementing important data logic.
8. Run relevant tests after changes.
9. Do not silently change the event schema.
10. If a website cannot be scraped reliably, document the limitation rather than creating brittle hacks.
11. Prefer official or structured sources.
12. Do not hallucinate event data.
13. Every displayed event must be traceable to at least one source URL.
14. Keep the frontend usable without JavaScript frameworks.
15. Optimize for maintainability and transparency rather than complexity.

---

# 40. Product Principle

The project should always optimize for:

> Signal over volume.

The system is successful when the user can open the page, spend 30 seconds looking at it, and understand what is worth knowing about in Munich today.

It is not successful merely because it collected a large number of events.