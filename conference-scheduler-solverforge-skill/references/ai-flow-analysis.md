# AI-Powered Educational Flow Analysis

Use Claude or another LLM to analyze talk summaries and determine optimal educational flow within tracks.

## Overview

The scheduler uses `talk.flow_order` to determine optimal ordering within a track. By default this is based on audience level (BEGINNER=1, INTERMEDIATE=2, ADVANCED=3), but you can use AI to compute more nuanced ordering based on talk summaries.

## Approach

### 1. Group Talks by Track

```python
from collections import defaultdict

tracks = defaultdict(list)
for talk in talks:
    tracks[talk.track_name].append(talk)
```

### 2. Create Prompt for Each Track

```python
def create_flow_prompt(track_name: str, track_talks: list) -> str:
    talks_desc = "\n".join([
        f"ID: {t.id}\nTitle: {t.title}\nLevel: {t.audience_level}\nSummary: {t.summary}\n"
        for t in track_talks
    ])

    return f"""Analyze these conference talks and suggest the optimal order for educational flow.

Consider:
- Topic relevance and logical progression
- Prerequisite knowledge (intro concepts before advanced)
- Technical level (BEGINNER, INTERMEDIATE, ADVANCED)
- Content building on previous talks

Track: {track_name}

Talks:
{talks_desc}

Return ONLY a comma-separated list of talk IDs in optimal order.
Example: 4367,5259,1411,4914"""
```

### 3. Call Claude API

```python
import anthropic

client = anthropic.Anthropic()

def get_flow_order(track_name: str, track_talks: list) -> list[str]:
    prompt = create_flow_prompt(track_name, track_talks)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse response
    order_str = response.content[0].text.strip()
    return [id.strip() for id in order_str.split(',')]
```

### 4. Apply to Talks

```python
def apply_ai_flow_order(talks: list, flow_orders: dict[str, list[str]]):
    """
    flow_orders: {"Track Name": ["id1", "id2", "id3"], ...}
    """
    for track_name, ordered_ids in flow_orders.items():
        for order, talk_id in enumerate(ordered_ids, start=1):
            for talk in talks:
                if talk.id == talk_id and talk.track_name == track_name:
                    talk.flow_order = order
                    break
```

### 5. Full Integration

```python
# Before solving
flow_orders = {}
for track_name, track_talks in tracks.items():
    if len(track_talks) > 1:
        ordered_ids = get_flow_order(track_name, track_talks)
        flow_orders[track_name] = ordered_ids

apply_ai_flow_order(talks, flow_orders)

# Now solve with AI-computed flow orders
problem = create_problem(timeslots, rooms, speakers, talks)
solution = solve(problem, time_limit_seconds=30)
```

## Example AI Response

For a "Java" track with talks about performance, modern features, design patterns, and Loom:

**Input talks:**
- 4945: A Glance At The Java Performance Toolbox (BEGINNER)
- 4931: Sailing Modern Java (INTERMEDIATE)
- 4929: Revisiting Design Patterns after 20 (INTERMEDIATE)
- 5261: Game of Loom (ADVANCED)
- 5456: Java Next - From Amber to Loom (ADVANCED)

**AI reasoning:**
1. Start with Performance Toolbox - foundational JDK knowledge
2. Modern Java features builds on basics
3. Design Patterns applies modern features
4. Java Next gives future perspective
5. Loom deep-dive is most advanced

**AI response:** `4945,4931,4929,5456,5261`

## Caching

Cache AI results to avoid repeated API calls:

```python
import json
from pathlib import Path

CACHE_FILE = Path("flow_order_cache.json")

def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}

def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))

def get_cached_flow_order(track_name: str, talk_ids: set) -> list[str] | None:
    cache = load_cache()
    key = f"{track_name}:{','.join(sorted(talk_ids))}"
    return cache.get(key)

def cache_flow_order(track_name: str, talk_ids: set, order: list[str]):
    cache = load_cache()
    key = f"{track_name}:{','.join(sorted(talk_ids))}"
    cache[key] = order
    save_cache(cache)
```

## Batch Processing

For large conferences, batch multiple tracks in one API call:

```python
def create_batch_prompt(tracks: dict[str, list]) -> str:
    sections = []
    for track_name, track_talks in tracks.items():
        talks_desc = "\n".join([
            f"  ID: {t.id}, Title: {t.title}, Level: {t.audience_level}"
            for t in track_talks
        ])
        sections.append(f"Track: {track_name}\n{talks_desc}")

    return f"""For each track below, provide the optimal talk order for educational flow.

{chr(10).join(sections)}

Return one line per track in format: TrackName: id1,id2,id3
"""
```

## Integration with scheduler.py

Add this to the main function before solving:

```python
def main():
    # ... read input ...

    # Optional: Apply AI flow ordering
    if os.environ.get('USE_AI_FLOW'):
        print("Computing AI-enhanced educational flow...")
        tracks = defaultdict(list)
        for talk in talks:
            tracks[talk.track_name].append(talk)

        for track_name, track_talks in tracks.items():
            if len(track_talks) > 1:
                try:
                    ordered_ids = get_flow_order(track_name, track_talks)
                    for order, talk_id in enumerate(ordered_ids, start=1):
                        for talk in track_talks:
                            if talk.id == talk_id:
                                talk.flow_order = order
                                break
                except Exception as e:
                    print(f"  Warning: AI flow analysis failed for {track_name}: {e}")

    # ... create problem and solve ...
```

Run with: `USE_AI_FLOW=1 python scheduler.py schedule.csv talks.csv output.csv`
