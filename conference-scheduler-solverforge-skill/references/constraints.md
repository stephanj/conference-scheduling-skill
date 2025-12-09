# Constraint Customization Guide

This guide explains how to customize the scheduling constraints using [SolverForge's](https://github.com/solverforge) constraint stream API.

## Constraint Types

### Hard Constraints
Must be satisfied or solution has hard score < 0. Implemented using `penalize(HardSoftScore.ONE_HARD)`.

### Soft Constraints
Optimization goals. Implemented using `penalize(HardSoftScore.ONE_SOFT)`. Lower soft score is better.

## Default Constraints

### Hard Constraints (in scheduler.py)

1. **Room conflict** - One talk per room per timeslot
2. **Speaker conflict** - Speaker can't be in two places simultaneously
3. **Track conflict** - Same track can't run in parallel
4. **Speaker availability** - Speaker must be available on scheduled day

### Soft Constraints

1. **Educational flow (level)** - Beginner talks before advanced within track
2. **Educational flow (order)** - Respect AI-computed flow order
3. **Track room consistency** - Keep same track in same room

## Adding Custom Constraints

### Example: Keynote in Main Room

```python
def keynote_in_main_room(constraint_factory: ConstraintFactory) -> Constraint:
    """Keynotes must be in Room 1."""
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(lambda a: a.talk.track_name == "Keynote")
        .filter(lambda a: a.room is not None and a.room.name != "Room 1")
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Keynote in main room")
    )
```

Add to `conference_constraints()`:
```python
return [
    # ... existing constraints ...
    keynote_in_main_room(constraint_factory),
]
```

### Example: First Slot Reserved for Opening

```python
def opening_in_first_slot(constraint_factory: ConstraintFactory) -> Constraint:
    """Opening talks must be in first timeslot."""
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(lambda a: a.talk.track_name == "Opening")
        .filter(lambda a: a.timeslot is not None and a.get_slot_index() != 0)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Opening in first slot")
    )
```

### Example: Prefer Morning for Beginner Talks

```python
def beginners_in_morning(constraint_factory: ConstraintFactory) -> Constraint:
    """Soft preference: beginner talks in morning (before 12:00)."""
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(lambda a: a.talk.audience_level == "BEGINNER")
        .filter(lambda a: a.timeslot is not None)
        .filter(lambda a: int(a.timeslot.from_hour.split(':')[0]) >= 12)
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Beginners in morning")
    )
```

### Example: Maximum Talks Per Speaker Per Day

```python
def max_talks_per_speaker_per_day(constraint_factory: ConstraintFactory) -> Constraint:
    """Soft penalty for speaker with more than 2 talks per day."""
    return (
        constraint_factory.for_each(TalkAssignment)
        .join(
            TalkAssignment,
            Joiners.equal(lambda a: a.get_day_index()),
            Joiners.filtering(
                lambda a1, a2: a1.id < a2.id and _has_speaker_overlap(a1.talk, a2.talk)
            ),
        )
        .join(
            TalkAssignment,
            Joiners.equal(
                lambda a1, a2: a1.get_day_index(),
                lambda a3: a3.get_day_index()
            ),
            Joiners.filtering(
                lambda a1, a2, a3: a3.id > a2.id and
                _has_speaker_overlap(a1.talk, a3.talk) and
                _has_speaker_overlap(a2.talk, a3.talk)
            ),
        )
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Max talks per speaker per day")
    )
```

### Example: Avoid Back-to-Back Talks for Same Speaker

```python
def speaker_break_between_talks(constraint_factory: ConstraintFactory) -> Constraint:
    """Soft penalty for same speaker in consecutive slots."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.get_day_index()),
        )
        .filter(lambda a1, a2: _has_speaker_overlap(a1.talk, a2.talk))
        .filter(lambda a1, a2: a1.timeslot is not None and a2.timeslot is not None)
        .filter(lambda a1, a2: abs(a1.get_slot_index() - a2.get_slot_index()) < 100)
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Speaker break between talks")
    )
```

## Constraint Weights

To prioritize constraints differently, use weighted penalties:

```python
def important_constraint(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(...)
        .penalize(HardSoftScore.of_soft(10))  # Weight of 10
        .as_constraint("Important soft constraint")
    )

def minor_constraint(constraint_factory: ConstraintFactory) -> Constraint:
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(...)
        .penalize(HardSoftScore.of_soft(1))   # Weight of 1
        .as_constraint("Minor soft constraint")
    )
```

## Constraint Stream Patterns

### Common Joiners

```python
# Match by value
Joiners.equal(lambda a: a.room)

# Filter with custom predicate
Joiners.filtering(lambda a1, a2: a1.id < a2.id)

# Less than / greater than
Joiners.less_than(lambda a: a.get_slot_index(), lambda b: b.get_slot_index())
```

### Common Patterns

```python
# For each entity
constraint_factory.for_each(TalkAssignment)

# For each unique pair (avoids counting conflicts twice)
constraint_factory.for_each_unique_pair(TalkAssignment, Joiners.equal(...))

# Join with another entity type
constraint_factory.for_each(TalkAssignment).join(Room, ...)

# Filter with lambda
.filter(lambda a: a.timeslot is not None)

# Penalize with weight
.penalize(HardSoftScore.ONE_HARD)
.penalize(HardSoftScore.of_soft(5))

# Name the constraint
.as_constraint("Constraint name")
```

## Debugging Constraints

To see which constraints are violated:

```python
from solverforge_legacy.solver import SolutionManager

solution_manager = SolutionManager.create(solver_factory)
score_analysis = solution_manager.analyze(solution)

for constraint in score_analysis.constraint_map.values():
    if constraint.score.soft_score < 0 or constraint.score.hard_score < 0:
        print(f"{constraint.constraint_name}: {constraint.score}")
        for match in constraint.matches:
            print(f"  - {match.justification}")
```
