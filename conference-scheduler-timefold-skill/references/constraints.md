# Constraint Customization Guide

This guide explains how to customize the scheduling constraints for your conference.

## Constraint Types

TimeFold uses two types of constraints:

### Hard Constraints (Must be satisfied)
Violations make the schedule invalid. The solver will always prioritize eliminating these.

### Soft Constraints (Optimization goals)  
The solver tries to minimize these but will accept violations if necessary.

## Default Constraints

### Hard Constraints

1. **Speaker Conflict** - A speaker cannot present in two rooms simultaneously
2. **Room Conflict** - Two talks cannot occupy the same room at the same time
3. **Track Conflict** - Same track cannot have talks in different rooms at the same time

### Soft Constraints

1. **Educational Flow (Level)** - Beginner talks before advanced within a track
2. **Educational Flow (Order)** - Respect AI-computed optimal order
3. **Track Room Consistency** - Keep same track in same room when possible

## Adding Custom Constraints

Edit `ConferenceConstraintProvider.java` to add constraints.

### Example: Keynote in Main Room

```java
Constraint keynoteInMainRoom(ConstraintFactory constraintFactory) {
    return constraintFactory
        .forEach(Talk.class)
        .filter(talk -> talk.getTrackName().equals("Keynote"))
        .filter(talk -> talk.getRoom() != null && !talk.getRoom().getName().equals("Room 1"))
        .penalize(HardSoftScore.ONE_HARD)
        .asConstraint("Keynote must be in Room 1");
}
```

### Example: Preferred Time for Track

```java
Constraint securityTracksAfternoon(ConstraintFactory constraintFactory) {
    return constraintFactory
        .forEach(Talk.class)
        .filter(talk -> talk.getTrackName().equals("Security"))
        .filter(talk -> talk.getTimeslot() != null 
            && talk.getTimeslot().getStartTime().getHour() < 13)
        .penalize(HardSoftScore.ONE_SOFT)
        .asConstraint("Security talks preferred in afternoon");
}
```

### Example: Speaker Preference

```java
Constraint speakerMorningPreference(ConstraintFactory constraintFactory) {
    return constraintFactory
        .forEach(Talk.class)
        .filter(talk -> talk.getSpeakerNames().contains("John Doe"))
        .filter(talk -> talk.getTimeslot() != null 
            && talk.getTimeslot().getStartTime().getHour() >= 14)
        .penalize(HardSoftScore.ofSoft(10))
        .asConstraint("John Doe prefers morning slots");
}
```

## Weighted Penalties

Use weighted scores for relative importance:

```java
.penalize(HardSoftScore.ofSoft(100))  // Very important soft constraint
.penalize(HardSoftScore.ofSoft(10))   // Medium importance
.penalize(HardSoftScore.ofSoft(1))    // Nice to have
```

## AI-Powered Flow Order

The `flowOrder` field on Talk can be set by AI analysis:

1. Group talks by track
2. Use an LLM to analyze summaries and suggest optimal order
3. Call `CsvDataReader.applyFlowOrder()` with the results

Example flow order map:
```java
Map<String, List<String>> flowOrders = Map.of(
    "Java", List.of("4945", "4931", "4929", "5456", "5261"),
    "Security", List.of("5298", "5268")
);
reader.applyFlowOrder(talks, flowOrders);
```

## Solver Tuning

Increase time limit for better solutions:
```bash
java -jar conference-scheduler.jar schedule.csv talks.csv --time-limit=5m
```

For large conferences (100+ talks), consider 10-30 minutes.
