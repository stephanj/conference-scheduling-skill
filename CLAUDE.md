# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains two implementations of a conference scheduler skill—tools that optimize conference schedules using constraint satisfaction:

1. **conference-scheduler-timefold-skill/** - Java/TimeFold implementation
2. **conference-scheduler-google-skill/** - Python/OR-Tools implementation

Both solve the same problem: given talks (with speakers, tracks, levels) and available time slots/rooms, produce an optimal schedule respecting hard constraints (no conflicts) and soft constraints (educational flow).

## Build & Run Commands

### Python (OR-Tools) Implementation

```bash
# Install dependency
pip install ortools --break-system-packages

# Run scheduler
python conference-scheduler-google-skill/assets/scheduler.py schedule.csv talks.csv output.csv --time-limit 30
```

### Java (TimeFold) Implementation

```bash
# Extract template, build, and run
unzip conference-scheduler-timefold-skill/assets/timefold-project.zip
cd timefold-conference-scheduler
mvn clean package
java -jar target/conference-scheduler-1.0-SNAPSHOT.jar schedule.csv talks.csv output.csv --time-limit=30s
```

## Input Format

Both implementations expect semicolon-delimited CSVs:

**Schedule CSV** (timeslots): `"day";"from hour";"to hour";"session type";"room name"` (day column optional for single-day)

**Talks CSV**: `"Talk ID";"Talk Title";"Audience Level";"Talk Summary";"Track Name";"Speaker Availability days";"Available from";"Available to";"Speaker names"`

## Architecture

### Constraint Model

**Hard Constraints** (must satisfy):
- Speaker conflict: same speaker can't present simultaneously
- Room conflict: one talk per room per timeslot
- Track conflict: same track can't run in parallel
- Speaker availability: respect day restrictions

**Soft Constraints** (optimization):
- Educational flow: BEGINNER → INTERMEDIATE → ADVANCED within track
- Track room consistency (TimeFold only): keep track in same room
- AI-computed flow order: respect LLM-determined talk sequence

### Key Files

- `conference-scheduler-google-skill/assets/scheduler.py` - Complete Python solver (dataclasses, CSV parsing, CP-SAT model, output generation)
- `conference-scheduler-timefold-skill/assets/timefold-project.zip` - Java project template with TimeFold solver
- `*/references/constraints.md` - Constraint customization examples
- `*/references/ai-flow-analysis.md` - LLM integration for optimal talk ordering

### AI Flow Enhancement

Both implementations support AI-enhanced educational flow:
1. Group talks by track
2. Send summaries to Claude with prompt requesting optimal order
3. Parse comma-separated talk IDs response
4. Apply to `flow_order` field before solving

## Solver Tuning

Time limits by conference size:
- Small (<30 talks): 10-30 seconds
- Medium (30-100 talks): 30-120 seconds
- Large (100+ talks): 2-10 minutes
