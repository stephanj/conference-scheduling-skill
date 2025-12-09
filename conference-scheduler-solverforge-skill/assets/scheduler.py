#!/usr/bin/env python3
"""
Conference Scheduler using SolverForge (Timefold compatible).
Optimizes conference schedules with constraints for speaker conflicts,
track distribution, room assignments, and educational flow.
Supports single-day and multi-day conferences.

SolverForge: https://github.com/solverforge
"""

import csv
import argparse
from dataclasses import dataclass, field
from typing import Optional, List, Annotated
from pathlib import Path

from solverforge_legacy.solver import SolverFactory
from solverforge_legacy.solver.config import (
    SolverConfig,
    ScoreDirectorFactoryConfig,
    TerminationConfig,
    Duration,
)
from solverforge_legacy.solver.domain import (
    planning_entity,
    planning_solution,
    PlanningId,
    PlanningVariable,
    PlanningEntityCollectionProperty,
    ProblemFactCollectionProperty,
    ValueRangeProvider,
    PlanningScore,
)
from solverforge_legacy.solver.score import (
    HardSoftScore,
    constraint_provider,
    Joiners,
    ConstraintFactory,
    Constraint,
)


# =============================================================================
# DOMAIN MODEL
# =============================================================================


@dataclass
class Timeslot:
    """A time window when talks can be scheduled."""
    id: Annotated[str, PlanningId]
    from_hour: str
    to_hour: str
    day_index: int = 0
    day_name: Optional[str] = None

    @property
    def slot_index(self) -> int:
        """Numeric index for ordering (day * 10000 + minutes from midnight)."""
        h, m = map(int, self.from_hour.split(':'))
        return self.day_index * 10000 + h * 60 + m

    @property
    def day_display(self) -> str:
        return self.day_name if self.day_name else f"Day {self.day_index + 1}"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Timeslot):
            return False
        return self.id == other.id


@dataclass
class Room:
    """A conference room where talks can be held."""
    id: Annotated[str, PlanningId]
    name: str

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Room):
            return False
        return self.id == other.id


@dataclass
class Speaker:
    """A speaker who may present one or more talks."""
    id: Annotated[str, PlanningId]
    name: str
    available_days: set = field(default_factory=set)

    def is_available_on(self, day_index: int) -> bool:
        """Check if speaker is available on given day. Empty set means all days."""
        return len(self.available_days) == 0 or day_index in self.available_days

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Speaker):
            return False
        return self.id == other.id


@dataclass
class TalkSpeaker:
    """Links a speaker to a talk (for proper constraint stream joins)."""
    id: Annotated[str, PlanningId]
    speaker: Speaker
    talk_id: str

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, TalkSpeaker):
            return False
        return self.id == other.id


@dataclass
class Talk:
    """A conference talk (problem fact - not the planning entity)."""
    id: Annotated[str, PlanningId]
    title: str
    summary: str
    track_name: str
    audience_level: str
    speakers: List[Speaker] = field(default_factory=list)
    flow_order: int = 0

    @property
    def level_order(self) -> int:
        """Numeric level for educational flow (lower = earlier)."""
        return {"BEGINNER": 1, "INTERMEDIATE": 2, "ADVANCED": 3}.get(
            self.audience_level.upper(), 2
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Talk):
            return False
        return self.id == other.id


@planning_entity
@dataclass
class TalkAssignment:
    """Planning entity: assigns a Talk to a Timeslot and Room."""
    id: Annotated[str, PlanningId]
    talk: Talk
    timeslot: Annotated[Optional[Timeslot], PlanningVariable] = None
    room: Annotated[Optional[Room], PlanningVariable] = None

    def get_slot_index(self) -> Optional[int]:
        if self.timeslot is None:
            return None
        return self.timeslot.slot_index

    def get_day_index(self) -> Optional[int]:
        if self.timeslot is None:
            return None
        return self.timeslot.day_index

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, TalkAssignment):
            return False
        return self.id == other.id


@planning_solution
@dataclass
class ConferenceSchedule:
    """The planning solution containing all problem facts and planning entities."""
    timeslots: Annotated[List[Timeslot], ProblemFactCollectionProperty, ValueRangeProvider]
    rooms: Annotated[List[Room], ProblemFactCollectionProperty, ValueRangeProvider]
    speakers: Annotated[List[Speaker], ProblemFactCollectionProperty]
    talk_speakers: Annotated[List[TalkSpeaker], ProblemFactCollectionProperty]
    talks: Annotated[List[Talk], ProblemFactCollectionProperty]
    talk_assignments: Annotated[List[TalkAssignment], PlanningEntityCollectionProperty]
    score: Annotated[Optional[HardSoftScore], PlanningScore] = None


# =============================================================================
# CONSTRAINTS
# =============================================================================


@constraint_provider
def conference_constraints(constraint_factory: ConstraintFactory) -> list[Constraint]:
    """Define all constraints for conference scheduling."""
    return [
        # Hard constraints
        room_conflict(constraint_factory),
        speaker_conflict(constraint_factory),
        track_conflict(constraint_factory),
        speaker_availability(constraint_factory),
        # Soft constraints
        educational_flow_level(constraint_factory),
        educational_flow_order(constraint_factory),
        track_room_consistency(constraint_factory),
    ]


# ===================== HARD CONSTRAINTS =====================


def room_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    """One talk per room per timeslot."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.room),
            Joiners.equal(lambda a: a.timeslot),
        )
        .filter(lambda a1, a2: a1.timeslot is not None and a1.room is not None)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Room conflict")
    )


def speaker_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    """Same speaker can't present simultaneously."""
    # Use TalkSpeaker linking table for proper constraint stream tracking.
    # Find pairs of TalkSpeakers with same speaker but different talks,
    # then join to their assignments and check for timeslot collision.
    return (
        constraint_factory.for_each_unique_pair(
            TalkSpeaker,
            Joiners.equal(lambda ts: ts.speaker),
        )
        .join(
            TalkAssignment,
            Joiners.equal(
                lambda ts1, ts2: ts1.talk_id,
                lambda a: a.talk.id,
            ),
        )
        .join(
            TalkAssignment,
            Joiners.equal(
                lambda ts1, ts2, a1: ts2.talk_id,
                lambda a: a.talk.id,
            ),
            Joiners.equal(
                lambda ts1, ts2, a1: a1.timeslot,
                lambda a: a.timeslot,
            ),
        )
        .filter(lambda ts1, ts2, a1, a2: a1.timeslot is not None)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Speaker conflict")
    )


def track_conflict(constraint_factory: ConstraintFactory) -> Constraint:
    """Same track can't run in parallel."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.talk.track_name),
            Joiners.equal(lambda a: a.timeslot),
        )
        .filter(lambda a1, a2: a1.timeslot is not None)
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Track conflict")
    )


def speaker_availability(constraint_factory: ConstraintFactory) -> Constraint:
    """Speaker must be available on scheduled day."""
    return (
        constraint_factory.for_each(TalkAssignment)
        .filter(lambda a: a.timeslot is not None)
        .filter(lambda a: not _all_speakers_available(a.talk, a.get_day_index()))
        .penalize(HardSoftScore.ONE_HARD)
        .as_constraint("Speaker availability")
    )


# ===================== SOFT CONSTRAINTS =====================


def educational_flow_level(constraint_factory: ConstraintFactory) -> Constraint:
    """Prefer BEGINNER before INTERMEDIATE before ADVANCED within track and day."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.talk.track_name),
            Joiners.equal(lambda a: a.get_day_index()),
        )
        .filter(lambda a1, a2: a1.timeslot is not None and a2.timeslot is not None)
        .filter(lambda a1, a2: _violates_level_flow(a1, a2))
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Educational flow (level)")
    )


def educational_flow_order(constraint_factory: ConstraintFactory) -> Constraint:
    """Respect AI-computed flow order within track and day."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.talk.track_name),
            Joiners.equal(lambda a: a.get_day_index()),
        )
        .filter(lambda a1, a2: a1.timeslot is not None and a2.timeslot is not None)
        .filter(lambda a1, a2: _violates_flow_order(a1, a2))
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Educational flow (order)")
    )


def track_room_consistency(constraint_factory: ConstraintFactory) -> Constraint:
    """Prefer keeping same track in same room on same day."""
    return (
        constraint_factory.for_each_unique_pair(
            TalkAssignment,
            Joiners.equal(lambda a: a.talk.track_name),
            Joiners.equal(lambda a: a.get_day_index()),
        )
        .filter(lambda a1, a2: a1.room is not None and a2.room is not None)
        .filter(lambda a1, a2: a1.room != a2.room)
        .penalize(HardSoftScore.ONE_SOFT)
        .as_constraint("Track room consistency")
    )


# ===================== HELPER FUNCTIONS =====================


def _all_speakers_available(talk: Talk, day_index: int) -> bool:
    """Check if all speakers of a talk are available on the given day."""
    if day_index is None:
        return True
    return all(s.is_available_on(day_index) for s in talk.speakers)


def _violates_level_flow(a1: TalkAssignment, a2: TalkAssignment) -> bool:
    """Check if a1 and a2 violate level-based educational flow."""
    level1 = a1.talk.level_order
    level2 = a2.talk.level_order
    slot1 = a1.get_slot_index()
    slot2 = a2.get_slot_index()
    if slot1 is None or slot2 is None:
        return False
    # Penalty if higher level comes before lower level
    if level1 > level2 and slot1 < slot2:
        return True
    if level2 > level1 and slot2 < slot1:
        return True
    return False


def _violates_flow_order(a1: TalkAssignment, a2: TalkAssignment) -> bool:
    """Check if a1 and a2 violate AI-computed flow order."""
    order1 = a1.talk.flow_order
    order2 = a2.talk.flow_order
    if order1 == order2 or order1 == 0 or order2 == 0:
        return False
    slot1 = a1.get_slot_index()
    slot2 = a2.get_slot_index()
    if slot1 is None or slot2 is None:
        return False
    # Penalty if higher order comes before lower order
    if order1 > order2 and slot1 < slot2:
        return True
    if order2 > order1 and slot2 < slot1:
        return True
    return False


# =============================================================================
# CSV PARSING
# =============================================================================


def read_schedule_csv(path: Path) -> tuple[list[Timeslot], list[Room], list[str]]:
    """Read schedule CSV, returns (timeslots, rooms, day_names)."""
    timeslots = []
    rooms_dict = {}
    day_map = {}

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        header = next(reader)

        # Detect if multi-day format (first column contains "day")
        has_day = header and 'day' in header[0].lower()
        day_col = 0 if has_day else -1
        from_col = 1 if has_day else 0
        to_col = 2 if has_day else 1
        room_col = 4 if has_day else 3

        seen_slots = set()
        for row in reader:
            if len(row) < (3 if has_day else 2):
                continue

            day_name = None
            day_index = 0
            if has_day:
                day_name = row[day_col].strip().strip('"')
                if day_name not in day_map:
                    day_map[day_name] = len(day_map)
                day_index = day_map[day_name]

            from_hour = row[from_col].strip().strip('"')
            to_hour = row[to_col].strip().strip('"')

            # Create unique timeslot ID
            slot_id = f"D{day_index}-{from_hour}-{to_hour}" if has_day else f"{from_hour}-{to_hour}"

            if slot_id not in seen_slots:
                seen_slots.add(slot_id)
                timeslots.append(Timeslot(
                    id=slot_id,
                    from_hour=from_hour,
                    to_hour=to_hour,
                    day_index=day_index,
                    day_name=day_name
                ))

            if len(row) > room_col:
                room_name = row[room_col].strip().strip('"')
                if room_name and room_name not in rooms_dict:
                    rooms_dict[room_name] = Room(id=room_name, name=room_name)

    timeslots.sort(key=lambda t: t.slot_index)
    rooms = list(rooms_dict.values())
    day_names = list(day_map.keys())

    return timeslots, rooms, day_names


def read_talks_csv(path: Path, day_names: list[str]) -> tuple[list[Speaker], list[TalkSpeaker], list[Talk]]:
    """Read talks CSV, returns (speakers, talk_speakers, talks)."""
    speakers_dict = {}
    talk_speaker_links = []
    talks = []

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        next(reader)  # Skip header

        for row in reader:
            if len(row) < 9:
                continue

            talk_id = row[0].strip().strip('"')
            title = row[1].strip().strip('"')
            level = row[2].strip().strip('"').upper() or "INTERMEDIATE"
            summary = row[3].strip().strip('"')
            track = row[4].strip().strip('"')
            avail_str = row[5].strip().strip('"') if len(row) > 5 else ""
            speaker_names_str = row[8].strip().strip('"')

            # Parse available days
            available_days = parse_available_days(avail_str, day_names)

            # Create speakers and TalkSpeaker links
            talk_speakers_list = []
            for name in speaker_names_str.split(','):
                name = name.strip()
                if not name:
                    continue
                speaker_id = name.lower().replace(' ', '_')
                if speaker_id not in speakers_dict:
                    speakers_dict[speaker_id] = Speaker(
                        id=speaker_id,
                        name=name,
                        available_days=available_days.copy()
                    )
                else:
                    # Merge availability (intersection would be more restrictive)
                    existing = speakers_dict[speaker_id]
                    if available_days:
                        if existing.available_days:
                            existing.available_days &= available_days
                        else:
                            existing.available_days = available_days.copy()

                speaker = speakers_dict[speaker_id]
                talk_speakers_list.append(speaker)

                # Create TalkSpeaker link for constraint stream
                link_id = f"{talk_id}-{speaker_id}"
                talk_speaker_links.append(TalkSpeaker(
                    id=link_id,
                    speaker=speaker,
                    talk_id=talk_id
                ))

            talk = Talk(
                id=talk_id,
                title=title,
                summary=summary,
                track_name=track,
                audience_level=level,
                speakers=talk_speakers_list,
                flow_order={"BEGINNER": 1, "INTERMEDIATE": 2, "ADVANCED": 3}.get(level, 2)
            )
            talks.append(talk)

    return list(speakers_dict.values()), talk_speaker_links, talks


def parse_available_days(avail_str: str, day_names: list[str]) -> set[int]:
    """Parse availability string like 'Wednesday,Thursday' or '1,2,3'."""
    available = set()
    for part in avail_str.replace(';', ',').split(','):
        part = part.strip().lower()
        if not part:
            continue

        # Try numeric
        try:
            available.add(int(part) - 1)  # Convert 1-based to 0-based
            continue
        except ValueError:
            pass

        # Try matching day names
        for i, day_name in enumerate(day_names):
            if part in day_name.lower() or day_name.lower() in part:
                available.add(i)
                break

    return available


# =============================================================================
# SOLVER
# =============================================================================


def create_problem(
    timeslots: list[Timeslot],
    rooms: list[Room],
    speakers: list[Speaker],
    talk_speakers: list[TalkSpeaker],
    talks: list[Talk]
) -> ConferenceSchedule:
    """Create the planning problem with unassigned talk assignments."""
    talk_assignments = [
        TalkAssignment(id=f"assign-{talk.id}", talk=talk)
        for talk in talks
    ]

    return ConferenceSchedule(
        timeslots=timeslots,
        rooms=rooms,
        speakers=speakers,
        talk_speakers=talk_speakers,
        talks=talks,
        talk_assignments=talk_assignments,
        score=None
    )


def solve(problem: ConferenceSchedule, time_limit_seconds: int) -> ConferenceSchedule:
    """Solve the conference scheduling problem."""
    solver_config = SolverConfig(
        solution_class=ConferenceSchedule,
        entity_class_list=[TalkAssignment],
        score_director_factory_config=ScoreDirectorFactoryConfig(
            constraint_provider_function=conference_constraints
        ),
        termination_config=TerminationConfig(
            spent_limit=Duration(seconds=time_limit_seconds)
        ),
    )

    solver = SolverFactory.create(solver_config).build_solver()
    return solver.solve(problem)


# =============================================================================
# OUTPUT
# =============================================================================


def write_csv_output(solution: ConferenceSchedule, path: Path, multi_day: bool):
    """Write schedule to CSV."""
    assignments = [a for a in solution.talk_assignments if a.timeslot and a.room]
    assignments.sort(key=lambda a: (a.timeslot.slot_index, a.room.name))

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)

        if multi_day:
            writer.writerow(['Day', 'Talk ID', 'From', 'To', 'Room', 'Title',
                           'Speakers', 'Level', 'Track'])
            for a in assignments:
                speakers_str = ", ".join(s.name for s in a.talk.speakers)
                writer.writerow([
                    a.timeslot.day_display, a.talk.id, a.timeslot.from_hour,
                    a.timeslot.to_hour, a.room.name, a.talk.title, speakers_str,
                    a.talk.audience_level, a.talk.track_name
                ])
        else:
            writer.writerow(['Talk ID', 'From', 'To', 'Room', 'Title',
                           'Speakers', 'Level', 'Track'])
            for a in assignments:
                speakers_str = ", ".join(s.name for s in a.talk.speakers)
                writer.writerow([
                    a.talk.id, a.timeslot.from_hour, a.timeslot.to_hour,
                    a.room.name, a.talk.title, speakers_str,
                    a.talk.audience_level, a.talk.track_name
                ])


def write_markdown_output(solution: ConferenceSchedule, path: Path, multi_day: bool):
    """Write schedule to Markdown."""
    assignments = [a for a in solution.talk_assignments if a.timeslot and a.room]
    assignments.sort(key=lambda a: (a.timeslot.slot_index, a.room.name))

    lines = ["# Conference Schedule\n"]
    current_day = -1
    current_slot = None

    for a in assignments:
        ts = a.timeslot

        # Day header for multi-day
        if multi_day and ts.day_index != current_day:
            current_day = ts.day_index
            current_slot = None
            lines.append(f"\n---\n\n# {ts.day_display}\n")

        # Timeslot header
        if ts.id != current_slot:
            current_slot = ts.id
            lines.append(f"\n## {ts.from_hour} - {ts.to_hour}\n")
            lines.append("\n| Room | ID | Title | Speaker | Level | Track |")
            lines.append("\n|------|-----|-------|---------|-------|-------|")

        title = a.talk.title.replace('|', '\\|')
        speakers_str = ", ".join(s.name for s in a.talk.speakers)
        lines.append(f"\n| {a.room.name} | {a.talk.id} | {title} | {speakers_str} | "
                    f"{a.talk.audience_level} | {a.talk.track_name} |")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def print_schedule(solution: ConferenceSchedule, multi_day: bool):
    """Print schedule to console."""
    assignments = [a for a in solution.talk_assignments if a.timeslot and a.room]
    assignments.sort(key=lambda a: (a.timeslot.slot_index, a.room.name))

    print("\n" + "=" * 100)
    print("CONFERENCE SCHEDULE")
    print("=" * 100)

    current_day = -1
    current_slot = None

    for a in assignments:
        ts = a.timeslot

        if multi_day and ts.day_index != current_day:
            current_day = ts.day_index
            current_slot = None
            print("\n" + "=" * 100)
            print(f">>> {ts.day_display.upper()} <<<")
            print("=" * 100)

        if ts.id != current_slot:
            current_slot = ts.id
            print("\n" + "-" * 100)
            print(f"TIME SLOT: {ts.from_hour} - {ts.to_hour}")
            print("-" * 100)

        title = a.talk.title[:50] + "..." if len(a.talk.title) > 50 else a.talk.title
        speakers_str = ", ".join(s.name for s in a.talk.speakers)
        speakers_str = speakers_str[:20] + "..." if len(speakers_str) > 20 else speakers_str
        print(f"  {a.room.name:10} | {a.talk.id:>5} | {title:50} | "
              f"{speakers_str:20} | {a.talk.audience_level:12} | {a.talk.track_name}")

    print("\n" + "=" * 100)


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description='Conference Scheduler using SolverForge (Timefold compatible)'
    )
    parser.add_argument('schedule_csv', help='CSV file with timeslots and rooms')
    parser.add_argument('talks_csv', help='CSV file with talk details')
    parser.add_argument('output_csv', nargs='?', default='schedule_output.csv',
                        help='Output CSV file')
    parser.add_argument('--time-limit', type=int, default=30,
                        help='Solver time limit in seconds')
    args = parser.parse_args()

    print("=" * 60)
    print("CONFERENCE SCHEDULER - Powered by SolverForge")
    print("=" * 60)

    # Read input
    print("\nReading input files...")
    timeslots, rooms, day_names = read_schedule_csv(Path(args.schedule_csv))
    speakers, talk_speakers, talks = read_talks_csv(Path(args.talks_csv), day_names)

    multi_day = len(day_names) > 1
    print(f"   - Days: {len(day_names) or 1}" +
          (f" ({', '.join(day_names)})" if day_names else ""))
    print(f"   - Timeslots: {len(timeslots)}")
    print(f"   - Rooms: {len(rooms)}")
    print(f"   - Talks: {len(talks)}")
    print(f"   - Speakers: {len(speakers)}")
    print(f"   - Tracks: {len(set(t.track_name for t in talks))}")

    # Check capacity
    capacity = len(timeslots) * len(rooms)
    if len(talks) > capacity:
        print(f"   Warning: More talks ({len(talks)}) than slots ({capacity})")

    # Create problem
    problem = create_problem(timeslots, rooms, speakers, talk_speakers, talks)

    # Solve
    print(f"\nSolving with time limit: {args.time_limit} seconds...")
    solution = solve(problem, args.time_limit)

    print(f"\nSolving complete!")
    print(f"   Score: {solution.score}")

    # Output
    print_schedule(solution, multi_day)

    output_path = Path(args.output_csv)
    write_csv_output(solution, output_path, multi_day)
    print(f"\nSchedule written to: {output_path}")

    md_path = output_path.with_suffix('.md')
    write_markdown_output(solution, md_path, multi_day)
    print(f"Markdown written to: {md_path}")


if __name__ == '__main__':
    main()
