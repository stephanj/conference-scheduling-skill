# Conference Scheduler Skills for Claude Code

Generate optimized conference schedules using constraint satisfaction solvers. These skills enable Claude Code to automatically schedule talks into time slots and rooms while respecting speaker availability, avoiding conflicts, and optimizing for educational flow.

## Available Skills

| Skill | Solver | Language | Best For |
|-------|--------|----------|----------|
| `conference-scheduler-timefold-skill` | TimeFold (OptaPlanner) | Java | Advanced constraints, large conferences |
| `conference-scheduler-google-skill` | OR-Tools CP-SAT | Python | Quick setup, no JVM required |

Both skills produce identical output formats and handle the same input data.

## Quick Start

### 1. Prepare Your Input Files

You need two CSV files (semicolon-delimited):

**Schedule CSV** — Available time slots and rooms:

```csv
"day";"from hour";"to hour";"session type";"room name"
"Wednesday";"09:30";"10:15";Conference;Room 1
"Wednesday";"09:30";"10:15";Conference;Room 2
"Wednesday";"10:35";"11:20";Conference;Room 1
"Thursday";"09:30";"10:15";Conference;Room 1
```

For single-day conferences, omit the "day" column.

**Talks CSV** — Talks to schedule:

```csv
"Talk ID";"Talk Title";"Audience Level";"Talk Summary";"Track Name";"Speaker Availability days";"Available from";"Available to";"Speaker names"
1411;Unit Test Your Architecture;BEGINNER;Learn ArchUnit...;Development Practices;Wednesday,Thursday;;;Roland Weisleder
3872;Full-stack Development;INTERMEDIATE;Java developers...;UI & UX;;;;Simon Martinelli
5456;Java Next;ADVANCED;Future of Java...;Java;Thursday;;;Nicolai Parlog
```

**Column Details:**
- **Talk ID**: Unique identifier
- **Audience Level**: BEGINNER, INTERMEDIATE, or ADVANCED
- **Track Name**: Groups related talks (same track won't run in parallel)
- **Speaker Availability days**: Comma-separated days (empty = all days)
- **Speaker names**: Comma-separated for multi-speaker talks

### 2. Use the Skill in Claude Code

Simply ask Claude Code to schedule your conference:

```
Schedule this conference using the talks in talks.csv and timeslots in schedule.csv
```

Or be more specific:

```
Create an optimized conference schedule from schedule.csv and talks.csv.
Use a 2-minute time limit for the solver. Output to wednesday-schedule.csv
```

### 3. Review Output

The skill generates:
- **CSV file**: Machine-readable schedule
- **Markdown file**: Human-readable schedule with tables

## What Gets Optimized

### Hard Constraints (Never Violated)

- **Speaker conflict**: A speaker cannot present in two rooms simultaneously
- **Room conflict**: Only one talk per room per time slot
- **Track conflict**: Same track cannot have parallel sessions
- **Speaker availability**: Respects day restrictions from input

### Soft Constraints (Optimized)

- **Educational flow**: BEGINNER → INTERMEDIATE → ADVANCED within each track
- **Track room consistency**: Keeps same track in same room when possible
- **AI-computed order**: Respects optimal talk sequence based on content analysis

## Installing the Skills

Claude Code skills are installed by copying the skill directory to your Claude Code configuration.

### 1. Locate Your Claude Code Skills Directory

Skills are stored in `~/.claude/skills/` (create if it doesn't exist):

```bash
mkdir -p ~/.claude/skills
```

### 2. Copy the Skill(s)

**For the Python/OR-Tools skill:**

```bash
cp -r conference-scheduler-google-skill ~/.claude/skills/
```

**For the Java/TimeFold skill:**

```bash
cp -r conference-scheduler-timefold-skill ~/.claude/skills/
```

### 3. Install Dependencies

**Python/OR-Tools skill:**

```bash
pip install ortools --break-system-packages
```

**Java/TimeFold skill** (requires Java 17+ and Maven):

```bash
cd ~/.claude/skills/conference-scheduler-timefold-skill
unzip assets/timefold-project.zip
cd timefold-conference-scheduler
mvn clean package
```

### 4. Verify Installation

Start a new Claude Code session. The skill should appear when you type `/` to see available commands, or Claude will automatically use it when you ask to schedule a conference.

## Recommended Time Limits

| Conference Size | Talks | Time Limit |
|-----------------|-------|------------|
| Small | < 30 | 10-30 seconds |
| Medium | 30-100 | 30-120 seconds |
| Large | 100+ | 2-10 minutes |

Longer time limits generally produce better optimization of soft constraints.

## Troubleshooting

### INFEASIBLE Status

The constraints cannot all be satisfied. Check for:
- More talks than available slots
- Speaker with more talks than available time slots on their available days
- Too many talks in same track for available parallel slots

### Talks Not Scheduled

Verify CSV formatting:
- Use semicolons as delimiters
- Quote fields containing special characters
- Ensure consistent day names between schedule and availability

### Speaker Availability Not Working

Ensure availability values match day names in schedule CSV exactly (e.g., "Wednesday" not "Wed").

## Customizing Constraints

See the `references/constraints.md` file in each skill directory for examples of adding custom constraints like:
- Keynotes in main room
- Track preferences for morning/afternoon
- Speaker time preferences
- Maximum talks per speaker per day

## AI-Enhanced Flow

For optimal educational flow beyond simple level ordering, the skills support AI analysis of talk summaries. See `references/ai-flow-analysis.md` for integration details.
