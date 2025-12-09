---
name: conference-scheduler
description: Generate optimized conference schedules using SolverForge (Timefold compatible). Use when the user needs to create conference schedules from CSV data with constraints like speaker conflicts, track distribution, room assignments, educational flow, and speaker availability. Supports both single-day and multi-day conferences. Python-native solution with no Java project setup required.
---

# Conference Scheduler Skill (SolverForge)

Generate optimized conference schedules using [SolverForge](https://github.com/solverforge) (Timefold compatible). Supports single-day and multi-day conferences.

## Quick Start

```bash
# Install dependencies (requires Python 3.10-3.12)
pip install solverforge_legacy --break-system-packages

# Run scheduler
python assets/scheduler.py schedule.csv talks.csv output.csv --time-limit 30
```

## Requirements

- Python 3.10, 3.11, or 3.12 (3.13+ not yet supported)
- JDK 17+ (for solver runtime)
- [solverforge_legacy](https://github.com/solverforge/solverforge-legacy) package

## Input Formats

### Single-Day Schedule CSV

```csv
"from hour";"to hour";"session type";"room name"
"10:35";"11:20";Conference;Room 2
"10:35";"11:20";Conference;Room 8
"11:30";"12:15";Conference;Room 3
```

### Multi-Day Schedule CSV

Add a "day" column as the first column:

```csv
"day";"from hour";"to hour";"session type";"room name"
"Wednesday";"09:30";"10:15";Conference;Room 1
"Wednesday";"10:35";"11:20";Conference;Room 2
"Thursday";"09:30";"10:15";Conference;Room 1
```

Day values can be: day names (Monday, Tuesday), dates (2024-03-15), or labels (Day 1, Day 2).

### Talks CSV

```csv
"Talk ID";"Talk Title";"Audience Level";"Talk Summary";"Track Name";"Speaker Availability days";"Available from";"Available to";"Speaker names"
1411;Unit Test Your Architecture;BEGINNER;ArchUnit is...;Development Practices;Wednesday,Thursday;;;Roland Weisleder
3872;Full-stack development;INTERMEDIATE;Java developers...;UI & UX;;;;Simon Martinelli
```

**Speaker Availability** formats (column 6):
- Day names: `Wednesday,Thursday`
- Day numbers: `1,2,3`
- Empty = available all days

## Constraints

### Hard Constraints (Must satisfy)

| Constraint | Description |
|------------|-------------|
| Speaker conflict | Same speaker can't be in two rooms at same time |
| Room conflict | Two talks can't be in same room at same time |
| Track conflict | Same track can't have talks in different rooms simultaneously |
| Speaker availability | Speaker must be available on scheduled day |

### Soft Constraints (Optimization)

| Constraint | Description |
|------------|-------------|
| Educational flow (level) | Beginner → Intermediate → Advanced within track per day |
| Educational flow (order) | Respect AI-computed optimal talk sequence |
| Track room consistency | Keep same track in same room on same day |

## Output

### CSV Output

Single-day:
```csv
"Talk ID";"From";"To";"Room";"Title";"Speakers";"Level";"Track"
```

Multi-day:
```csv
"Day";"Talk ID";"From";"To";"Room";"Title";"Speakers";"Level";"Track"
```

### Markdown Output

Generated alongside CSV with `.md` extension, includes tables grouped by timeslot (and day for multi-day).

## Time Limits

- Small conferences (< 30 talks): 10-30 seconds
- Medium conferences (30-100 talks): 30-120 seconds
- Large conferences (100+ talks): 2-10 minutes

## Troubleshooting

### Hard score < 0

The schedule has constraint violations. Check for:
- More talks than available slots
- Speaker assigned to multiple talks in same slot
- Speaker not available on scheduled day
- Too many talks in same track for available parallel slots

Increase time limit or review input data.

### Talks not scheduled

Verify CSV parsing - check semicolon separators and quote handling.

### Speaker availability not working

Ensure the "Speaker Availability days" column values match the day names in your schedule CSV (e.g., if schedule uses "Wednesday", availability should use "Wednesday" not "Wed").

### JVM/Java errors

Ensure JDK 17+ is installed and JAVA_HOME is set correctly.

---

*Powered by [SolverForge](https://github.com/solverforge)*
