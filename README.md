# Conference Scheduler Skills for Claude Code

Generate optimized conference schedules using constraint satisfaction solvers. These skills enable Claude Code to automatically schedule talks into time slots and rooms while respecting speaker availability, avoiding conflicts, and optimizing for educational flow.

## Example : Create the perfect schedule

<img width="1579" height="973" alt="Screenshot 2025-12-09 at 10 48 53" src="https://github.com/user-attachments/assets/f4f0e941-dc14-4e9f-ac71-dd0c096437af" />

<img width="1579" height="627" alt="Screenshot 2025-12-09 at 10 49 12" src="https://github.com/user-attachments/assets/7b148168-febe-49a0-95d0-83e953819b42" />

<img width="1579" height="678" alt="Screenshot 2025-12-09 at 10 49 26" src="https://github.com/user-attachments/assets/d2f02a41-f37a-451e-b6f0-9b7fae25a1ac" />

See example directory for the used input files and the generated output schedule.

## Available Skills

| Skill | Solver | Language | Best For |
|-------|--------|----------|----------|
| `conference-scheduler-timefold-skill` | TimeFold (OptaPlanner) | Java | Advanced constraints, large conferences |
| `conference-scheduler-google-skill` | OR-Tools CP-SAT | Python | Quick setup, no JVM required |
| `conference-scheduler-solverforge-skill` | [SolverForge](https://github.com/solverforge) | Python | Timefold-compatible, Python-native |

All skills produce identical output formats and handle the same input data.

## Example

See the [example/](example/) directory for complete working examples:

| File | Description |
|------|-------------|
| [example/input/schedule.csv](example/input/schedule.csv) | Sample timeslots and rooms (single-day conference) |
| [example/input/talks.csv](example/input/talks.csv) | Sample talks with 24 sessions across multiple tracks |
| [example/output/output.csv](example/output/output.csv) | Generated schedule (CSV format) |
| [example/output/output.md](example/output/output.md) | Generated schedule (Markdown format) |

## Quick Start

### 1. Prepare Your Input Files

You need two CSV files (semicolon-delimited). See [example/input/](example/input/) for complete examples.

**Schedule CSV** — Available time slots and rooms ([example](example/input/schedule.csv)):

```csv
"from hour";"to hour";"session type";"room name"
"10:35";"11:20";Conference;Room 2
"10:35";"11:20";Conference;Room 8
"11:30";"12:15";Conference;Room 3
```

For multi-day conferences, add a "day" column as the first column.

**Talks CSV** — Talks to schedule ([example](example/input/talks.csv)):

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
- **CSV file**: Machine-readable schedule ([example](example/output/output.csv))
- **Markdown file**: Human-readable schedule with tables ([example](example/output/output.md))

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

**For the Python/SolverForge skill:**

```bash
cp -r conference-scheduler-solverforge-skill ~/.claude/skills/
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

**Python/SolverForge skill** (requires Python 3.10-3.12 and JDK 17+):

```bash
pip install solverforge_legacy --break-system-packages
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

See the constraints documentation for examples of adding custom constraints:
- [Python/OR-Tools constraints](conference-scheduler-google-skill/references/constraints.md)
- [Java/TimeFold constraints](conference-scheduler-timefold-skill/references/constraints.md)
- [Python/SolverForge constraints](conference-scheduler-solverforge-skill/references/constraints.md)

Examples include:
- Keynotes in main room
- Track preferences for morning/afternoon
- Speaker time preferences
- Maximum talks per speaker per day

## AI-Enhanced Flow

For optimal educational flow beyond simple level ordering, the skills support AI analysis of talk summaries:
- [Python/OR-Tools AI integration](conference-scheduler-google-skill/references/ai-flow-analysis.md)
- [Java/TimeFold AI integration](conference-scheduler-timefold-skill/references/ai-flow-analysis.md)
- [Python/SolverForge AI integration](conference-scheduler-solverforge-skill/references/ai-flow-analysis.md)
