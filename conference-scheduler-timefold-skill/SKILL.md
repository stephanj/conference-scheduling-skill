---
name: conference-scheduler
description: Generate optimized conference schedules using TimeFold (formerly OptaPlanner). Use when the user needs to create conference schedules from CSV data with constraints like speaker conflicts, track distribution, room assignments, educational flow, and speaker availability. Supports both single-day and multi-day conferences. Handles inputs from Google Sheets CSV exports with talks (ID, title, summary, track, level, speakers, availability) and schedule slots (day, times, rooms). Outputs CSV and Markdown schedules.
---

# Conference Scheduler Skill

Generate optimized conference schedules using TimeFold constraint solver with AI-enhanced educational flow. Supports single-day and multi-day conferences.

## Quick Start

1. Extract the template project: `unzip assets/timefold-project.zip`
2. Provide two CSV files:
   - **Schedule CSV**: Available time slots and rooms (with optional day column)
   - **Talks CSV**: Talks to schedule with metadata
3. Run the solver
4. Get optimized schedule as CSV and Markdown

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
"Thursday";"10:35";"11:20";Conference;Room 2
"Friday";"09:30";"10:15";Conference;Room 1
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
- Day labels: `Day 1,Day 2`
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
| Track day consistency | Keep same track on same day when possible |

## Usage

### Build and Run

```bash
cd timefold-conference-scheduler
mvn clean package
java -jar target/conference-scheduler-1.0-SNAPSHOT.jar schedule.csv talks.csv output.csv --time-limit=30s
```

### Time Limits

- Small conferences (< 30 talks): 30 seconds
- Medium conferences (30-100 talks): 2-5 minutes  
- Large conferences (100+ talks, multi-day): 10-30 minutes

## Output Format

### Single-Day CSV Output

```csv
"Talk ID";"From";"To";"Room";"Title";"Speakers";"Level";"Track"
"4367";"10:35";"11:20";"Room 2";"BDD Talk";"Katrin Rabow";"BEGINNER";"Development Practices"
```

### Multi-Day CSV Output

```csv
"Day";"Talk ID";"From";"To";"Room";"Title";"Speakers";"Level";"Track"
"Wednesday";"4367";"10:35";"11:20";"Room 2";"BDD Talk";"Katrin Rabow";"BEGINNER";"Development Practices"
"Thursday";"5456";"09:30";"10:15";"Room 1";"Java Next";"Nicolai Parlog";"ADVANCED";"Java"
```

### Markdown Output

Multi-day schedules include day headers:

```markdown
# Wednesday

## 10:35 - 11:20

| Room | Talk ID | Title | Speaker | Level | Track |
|------|---------|-------|---------|-------|-------|
| Room 2 | 4367 | BDD Talk | Katrin Rabow | BEGINNER | Development Practices |

---

# Thursday

## 09:30 - 10:15

| Room | Talk ID | Title | Speaker | Level | Track |
|------|---------|-------|---------|-------|-------|
| Room 1 | 5456 | Java Next | Nicolai Parlog | ADVANCED | Java |
```

## AI-Enhanced Flow

For optimal educational flow within tracks, use AI to analyze talk summaries:

1. Group talks by track
2. Send summaries to LLM with prompt requesting optimal order
3. Apply order using `CsvDataReader.applyFlowOrder()`

See `references/ai-flow-analysis.md` for integration details.

## Customization

### Adding Constraints

Edit `ConferenceConstraintProvider.java`. Example keynote constraint:

```java
Constraint keynoteInMainRoom(ConstraintFactory factory) {
    return factory.forEach(Talk.class)
        .filter(t -> t.getTrackName().equals("Keynote"))
        .filter(t -> !t.getRoom().getName().equals("Room 1"))
        .penalize(HardSoftScore.ONE_HARD)
        .asConstraint("Keynote in main room");
}
```

See `references/constraints.md` for more examples.

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
