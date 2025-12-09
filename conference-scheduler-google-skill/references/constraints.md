# Constraint Customization Guide

This guide explains how to customize the scheduling constraints.

## Constraint Types

### Hard Constraints
Must be satisfied or solution is INFEASIBLE. Implemented as `model.Add()` constraints in OR-Tools.

### Soft Constraints  
Optimization goals. Implemented via `model.Minimize()` with penalty variables.

## Default Constraints

### Hard Constraints (in scheduler.py)

1. **Room conflict** - One talk per room per timeslot
2. **Speaker conflict** - Speaker can't be in two places simultaneously  
3. **Track conflict** - Same track can't run in parallel
4. **Speaker availability** - Speaker must be available on scheduled day

### Soft Constraints

1. **Educational flow** - Beginner talks before advanced within track

## Adding Custom Constraints

### Example: Keynote in Main Room

```python
# After creating the model, add:
for t, talk in enumerate(talks):
    if talk.track_name == "Keynote":
        main_room_idx = room_idx["Room 1"]  # or whatever your main room is
        for s in range(num_timeslots):
            for r in range(num_rooms):
                if r != main_room_idx:
                    model.Add(assign[(t, s, r)] == 0)
```

### Example: First Slot Reserved for Opening

```python
# Forbid regular talks in first timeslot
first_slot = 0
for t, talk in enumerate(talks):
    if talk.track_name != "Opening":
        for r in range(num_rooms):
            model.Add(assign[(t, first_slot, r)] == 0)
```

### Example: Maximum Talks Per Speaker Per Day

```python
# Group talks by speaker
from collections import defaultdict
speaker_talks = defaultdict(list)
for t, talk in enumerate(talks):
    for speaker in talk.speakers_list():
        speaker_talks[speaker.lower()].append(t)

# Limit to 2 talks per speaker per day
max_per_day = 2
for speaker, talk_indices in speaker_talks.items():
    if len(talk_indices) > max_per_day:
        # Group timeslots by day
        day_slots = defaultdict(list)
        for s, ts in enumerate(timeslots):
            day_slots[ts.day_index].append(s)
        
        for day_idx, slots in day_slots.items():
            # Sum of all assignments for this speaker on this day <= max_per_day
            model.Add(
                sum(assign[(t, s, r)] 
                    for t in talk_indices 
                    for s in slots 
                    for r in range(num_rooms)) <= max_per_day
            )
```

### Example: Track Room Consistency (Soft)

```python
# Penalty for same track in different rooms on same day
track_room_penalties = []
for track, track_talk_indices in track_talks.items():
    if len(track_talk_indices) > 1:
        for i, t1 in enumerate(track_talk_indices):
            for t2 in track_talk_indices[i+1:]:
                # Create penalty variable for room mismatch
                for r1 in range(num_rooms):
                    for r2 in range(num_rooms):
                        if r1 != r2:
                            # Both assigned AND different rooms
                            both_assigned = model.NewBoolVar(f'both_{t1}_{t2}_{r1}_{r2}')
                            # This is complex - simplified version:
                            pass  # Add penalty logic here

# Add to objective
model.Minimize(sum(soft_penalties) + sum(track_room_penalties))
```

## Soft Constraint Weights

To prioritize constraints differently:

```python
# Weight educational flow violations more heavily
model.Minimize(
    2 * sum(flow_violations) +    # Educational flow (weight 2)
    1 * sum(room_consistency)      # Room consistency (weight 1)
)
```
