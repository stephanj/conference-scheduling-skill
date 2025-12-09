#!/usr/bin/env python3
"""
Conference Scheduler using Google OR-Tools CP-SAT Solver.
Optimizes conference schedules with constraints for speaker conflicts, 
track distribution, room assignments, and educational flow.
Supports single-day and multi-day conferences.
"""

import csv
import argparse
from dataclasses import dataclass, field
from typing import Optional
from ortools.sat.python import cp_model
from pathlib import Path


@dataclass
class Timeslot:
    id: str
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

    def __hash__(self):
        return hash(self.id)


@dataclass
class Room:
    name: str

    def __hash__(self):
        return hash(self.name)


@dataclass 
class Talk:
    id: str
    title: str
    summary: str
    track_name: str
    audience_level: str  # BEGINNER, INTERMEDIATE, ADVANCED
    speaker_names: str
    available_days: set = field(default_factory=set)  # Empty = all days
    flow_order: int = 0  # For AI-computed ordering within track
    
    # Assigned by solver
    timeslot: Optional[Timeslot] = None
    room: Optional[Room] = None

    @property
    def level_order(self) -> int:
        """Numeric level for educational flow (lower = earlier)."""
        return {"BEGINNER": 1, "INTERMEDIATE": 2, "ADVANCED": 3}.get(
            self.audience_level.upper(), 2
        )

    def is_available_on(self, day_index: int) -> bool:
        """Check if speaker is available on given day."""
        return len(self.available_days) == 0 or day_index in self.available_days

    def speakers_list(self) -> list[str]:
        """Get list of individual speakers."""
        return [s.strip() for s in self.speaker_names.split(',') if s.strip()]

    def __hash__(self):
        return hash(self.id)


def read_schedule_csv(path: Path) -> tuple[list[Timeslot], list[Room], list[str]]:
    """Read schedule CSV, returns (timeslots, rooms, day_names)."""
    timeslots = []
    rooms_set = set()
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
                timeslots.append(Timeslot(slot_id, from_hour, to_hour, day_index, day_name))
            
            if len(row) > room_col:
                room_name = row[room_col].strip().strip('"')
                if room_name:
                    rooms_set.add(room_name)
    
    timeslots.sort(key=lambda t: t.slot_index)
    rooms = [Room(name) for name in sorted(rooms_set)]
    day_names = list(day_map.keys())
    
    return timeslots, rooms, day_names


def read_talks_csv(path: Path, day_names: list[str]) -> list[Talk]:
    """Read talks CSV."""
    talks = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        next(reader)  # Skip header
        
        for row in reader:
            if len(row) < 9:
                continue
            
            talk = Talk(
                id=row[0].strip().strip('"'),
                title=row[1].strip().strip('"'),
                summary=row[3].strip().strip('"'),
                track_name=row[4].strip().strip('"'),
                audience_level=row[2].strip().strip('"').upper() or "INTERMEDIATE",
                speaker_names=row[8].strip().strip('"'),
            )
            
            # Parse available days
            avail_str = row[5].strip().strip('"') if len(row) > 5 else ""
            if avail_str:
                talk.available_days = parse_available_days(avail_str, day_names)
            
            # Default flow order based on level
            talk.flow_order = talk.level_order
            
            talks.append(talk)
    
    return talks


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


def has_speaker_overlap(talk1: Talk, talk2: Talk) -> bool:
    """Check if two talks share any speaker."""
    speakers1 = set(s.lower() for s in talk1.speakers_list())
    speakers2 = set(s.lower() for s in talk2.speakers_list())
    return bool(speakers1 & speakers2)


def solve_schedule(
    timeslots: list[Timeslot],
    rooms: list[Room], 
    talks: list[Talk],
    time_limit_seconds: int = 30
) -> tuple[list[Talk], str]:
    """
    Solve the conference scheduling problem using OR-Tools CP-SAT.
    Returns (scheduled_talks, status_message).
    """
    model = cp_model.CpModel()
    
    num_talks = len(talks)
    num_timeslots = len(timeslots)
    num_rooms = len(rooms)
    
    # Create indices
    timeslot_idx = {t.id: i for i, t in enumerate(timeslots)}
    room_idx = {r.name: i for i, r in enumerate(rooms)}
    
    # Decision variables: assign[talk][timeslot][room] = 1 if talk is assigned there
    assign = {}
    for t in range(num_talks):
        for s in range(num_timeslots):
            for r in range(num_rooms):
                assign[(t, s, r)] = model.NewBoolVar(f'assign_t{t}_s{s}_r{r}')
    
    # Each talk must be assigned to exactly one slot+room
    for t in range(num_talks):
        model.AddExactlyOne(assign[(t, s, r)] 
                           for s in range(num_timeslots) 
                           for r in range(num_rooms))
    
    # HARD CONSTRAINT: Room conflict - max one talk per room per timeslot
    for s in range(num_timeslots):
        for r in range(num_rooms):
            model.AddAtMostOne(assign[(t, s, r)] for t in range(num_talks))
    
    # HARD CONSTRAINT: Speaker conflict - same speaker can't be in two places
    for t1 in range(num_talks):
        for t2 in range(t1 + 1, num_talks):
            if has_speaker_overlap(talks[t1], talks[t2]):
                for s in range(num_timeslots):
                    # Can't both be in same timeslot (any room)
                    model.AddAtMostOne(
                        [assign[(t1, s, r)] for r in range(num_rooms)] +
                        [assign[(t2, s, r)] for r in range(num_rooms)]
                    )
    
    # HARD CONSTRAINT: Track conflict - same track can't run in parallel
    track_talks = {}
    for t, talk in enumerate(talks):
        track_talks.setdefault(talk.track_name, []).append(t)
    
    for track, track_talk_indices in track_talks.items():
        if len(track_talk_indices) > 1:
            for s in range(num_timeslots):
                # At most one talk from this track in this timeslot
                model.AddAtMostOne(
                    assign[(t, s, r)]
                    for t in track_talk_indices
                    for r in range(num_rooms)
                )
    
    # HARD CONSTRAINT: Speaker availability
    for t, talk in enumerate(talks):
        if talk.available_days:
            for s, timeslot in enumerate(timeslots):
                if timeslot.day_index not in talk.available_days:
                    # Speaker not available this day - forbid all rooms
                    for r in range(num_rooms):
                        model.Add(assign[(t, s, r)] == 0)
    
    # SOFT CONSTRAINTS - Educational flow
    # Create helper variables for timeslot assignment
    talk_timeslot = {}
    for t in range(num_talks):
        talk_timeslot[t] = model.NewIntVar(0, num_timeslots - 1, f'timeslot_{t}')
        model.Add(talk_timeslot[t] == sum(
            s * assign[(t, s, r)]
            for s in range(num_timeslots)
            for r in range(num_rooms)
        ))
    
    # Soft constraint penalties
    soft_penalties = []
    
    # Educational flow: within same track and day, prefer beginner before advanced
    for track, track_talk_indices in track_talks.items():
        if len(track_talk_indices) > 1:
            for i, t1 in enumerate(track_talk_indices):
                for t2 in enumerate(track_talk_indices[i+1:]):
                    t2_idx = track_talk_indices[i + 1 + t2[0]]
                    level1 = talks[t1].level_order
                    level2 = talks[t2_idx].level_order
                    
                    if level1 != level2:
                        # Penalty if higher level comes before lower level
                        violation = model.NewBoolVar(f'flow_violation_{t1}_{t2_idx}')
                        if level1 > level2:
                            # t1 has higher level, should come after t2
                            model.Add(talk_timeslot[t1] < talk_timeslot[t2_idx]).OnlyEnforceIf(violation)
                            model.Add(talk_timeslot[t1] >= talk_timeslot[t2_idx]).OnlyEnforceIf(violation.Not())
                        else:
                            # t1 has lower level, should come before t2
                            model.Add(talk_timeslot[t1] > talk_timeslot[t2_idx]).OnlyEnforceIf(violation)
                            model.Add(talk_timeslot[t1] <= talk_timeslot[t2_idx]).OnlyEnforceIf(violation.Not())
                        
                        soft_penalties.append(violation)
    
    # Minimize soft constraint violations
    if soft_penalties:
        model.Minimize(sum(soft_penalties))
    
    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)
    
    status_names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE", 
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN"
    }
    status_msg = status_names.get(status, "UNKNOWN")
    
    # Extract solution
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for t, talk in enumerate(talks):
            for s in range(num_timeslots):
                for r in range(num_rooms):
                    if solver.Value(assign[(t, s, r)]) == 1:
                        talk.timeslot = timeslots[s]
                        talk.room = rooms[r]
                        break
        
        soft_score = -int(solver.ObjectiveValue()) if soft_penalties else 0
        status_msg = f"{status_msg} (soft penalty: {-soft_score})"
    
    return talks, status_msg


def write_csv_output(talks: list[Talk], path: Path, multi_day: bool):
    """Write schedule to CSV."""
    scheduled = [t for t in talks if t.timeslot and t.room]
    scheduled.sort(key=lambda t: (t.timeslot.slot_index, t.room.name))
    
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
        
        if multi_day:
            writer.writerow(['Day', 'Talk ID', 'From', 'To', 'Room', 'Title', 'Speakers', 'Level', 'Track'])
            for t in scheduled:
                writer.writerow([
                    t.timeslot.day_display, t.id, t.timeslot.from_hour, t.timeslot.to_hour,
                    t.room.name, t.title, t.speaker_names, t.audience_level, t.track_name
                ])
        else:
            writer.writerow(['Talk ID', 'From', 'To', 'Room', 'Title', 'Speakers', 'Level', 'Track'])
            for t in scheduled:
                writer.writerow([
                    t.id, t.timeslot.from_hour, t.timeslot.to_hour,
                    t.room.name, t.title, t.speaker_names, t.audience_level, t.track_name
                ])


def write_markdown_output(talks: list[Talk], path: Path, multi_day: bool):
    """Write schedule to Markdown."""
    scheduled = [t for t in talks if t.timeslot and t.room]
    scheduled.sort(key=lambda t: (t.timeslot.slot_index, t.room.name))
    
    lines = ["# Conference Schedule\n"]
    
    current_day = -1
    current_slot = None
    
    for talk in scheduled:
        ts = talk.timeslot
        
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
        
        title = talk.title.replace('|', '\\|')
        lines.append(f"\n| {talk.room.name} | {talk.id} | {title} | {talk.speaker_names} | {talk.audience_level} | {talk.track_name} |")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def print_schedule(talks: list[Talk], multi_day: bool):
    """Print schedule to console."""
    scheduled = [t for t in talks if t.timeslot and t.room]
    scheduled.sort(key=lambda t: (t.timeslot.slot_index, t.room.name))
    
    print("\n" + "=" * 100)
    print("CONFERENCE SCHEDULE")
    print("=" * 100)
    
    current_day = -1
    current_slot = None
    
    for talk in scheduled:
        ts = talk.timeslot
        
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
        
        title = talk.title[:50] + "..." if len(talk.title) > 50 else talk.title
        speaker = talk.speaker_names[:20] + "..." if len(talk.speaker_names) > 20 else talk.speaker_names
        print(f"  {talk.room.name:10} | {talk.id:>5} | {title:50} | {speaker:20} | {talk.audience_level:12} | {talk.track_name}")
    
    print("\n" + "=" * 100)


def main():
    parser = argparse.ArgumentParser(description='Conference Scheduler using OR-Tools')
    parser.add_argument('schedule_csv', help='CSV file with timeslots and rooms')
    parser.add_argument('talks_csv', help='CSV file with talk details')
    parser.add_argument('output_csv', nargs='?', default='schedule_output.csv', help='Output CSV file')
    parser.add_argument('--time-limit', type=int, default=30, help='Solver time limit in seconds')
    args = parser.parse_args()
    
    print("=" * 60)
    print("CONFERENCE SCHEDULER - Powered by OR-Tools CP-SAT")
    print("=" * 60)
    
    # Read input
    print("\n📖 Reading input files...")
    timeslots, rooms, day_names = read_schedule_csv(Path(args.schedule_csv))
    talks = read_talks_csv(Path(args.talks_csv), day_names)
    
    multi_day = len(day_names) > 1
    print(f"   - Days: {len(day_names) or 1}" + (f" ({', '.join(day_names)})" if day_names else ""))
    print(f"   - Timeslots: {len(timeslots)}")
    print(f"   - Rooms: {len(rooms)}")
    print(f"   - Talks: {len(talks)}")
    print(f"   - Tracks: {len(set(t.track_name for t in talks))}")
    
    # Check capacity
    capacity = len(timeslots) * len(rooms)
    if len(talks) > capacity:
        print(f"⚠️  Warning: More talks ({len(talks)}) than slots ({capacity})")
    
    # Solve
    print(f"\n⏱️  Solving with time limit: {args.time_limit} seconds...")
    talks, status = solve_schedule(timeslots, rooms, talks, args.time_limit)
    
    print(f"\n✅ Solving complete!")
    print(f"   Status: {status}")
    
    # Output
    print_schedule(talks, multi_day)
    
    output_path = Path(args.output_csv)
    write_csv_output(talks, output_path, multi_day)
    print(f"\n📄 Schedule written to: {output_path}")
    
    md_path = output_path.with_suffix('.md')
    write_markdown_output(talks, md_path, multi_day)
    print(f"📄 Markdown written to: {md_path}")


if __name__ == '__main__':
    main()
