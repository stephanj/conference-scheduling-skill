# AI-Powered Educational Flow Analysis

This guide explains how to use AI/LLM to analyze talk summaries and determine optimal educational flow ordering within tracks.

## Overview

The educational flow constraint ensures talks within a track are ordered for optimal learning. While audience level (beginner → advanced) provides a baseline, analyzing talk summaries with AI enables more nuanced ordering that accounts for topic dependencies, conceptual progression, and variety.

## Approach

### 1. Group Talks by Track

```java
Map<String, List<Talk>> talksByTrack = talks.stream()
    .collect(Collectors.groupingBy(Talk::getTrackName));
```

### 2. Prompt Template for AI Analysis

For each track, send this prompt to an LLM:

```
Analyze these conference talks and suggest the optimal order for educational flow.
Consider:
- Topic relevance and logical progression
- Prerequisite knowledge (intro concepts before advanced)
- Technical level (BEGINNER, INTERMEDIATE, ADVANCED)
- Variety and engagement

Track: {trackName}

Talks:
{for each talk}
ID: {id}
Title: {title}
Level: {level}
Summary: {summary}
{end for}

Return ONLY a comma-separated list of talk IDs in optimal order.
Example: 4367,5259,1411,4914
```

### 3. Parse AI Response

```java
String aiResponse = "4367,5259,1411,4914";
List<String> orderedIds = Arrays.asList(aiResponse.split(","))
    .stream()
    .map(String::trim)
    .toList();
```

### 4. Apply to Solver via `CsvReader.applyFlowOrder()`

```java
CsvReader reader = new CsvReader();
Schedule problem = reader.readProblem(schedulePath, talksPath);

// Build flow orders map: track name → ordered list of talk IDs
Map<String, List<String>> flowOrders = new HashMap<>();
flowOrders.put("Development Practices", List.of("4367", "5259", "1411", "4914"));
flowOrders.put("Java", List.of("4945", "4931", "4929", "5456", "5261"));
// ... add more tracks as needed

// Apply before solving
reader.applyFlowOrder(problem.getTalks(), flowOrders);

// Then solve as normal
```

> **Note**: `applyFlowOrder()` is defined in `CsvReader` and sets the `flowOrder` field on each `Talk`.
> Talks not present in `flowOrders` retain their default order (derived from audience level).

## Integration with Claude API

### Using the Anthropic Java SDK

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.models.*;

public class FlowAnalyzer {
    private final AnthropicClient client = AnthropicOkHttpClient.fromEnv();

    public List<String> analyzeTrackFlow(String trackName, List<Talk> talks) {
        String prompt = buildPrompt(trackName, talks);

        Message response = client.messages().create(
            MessageCreateParams.builder()
                .model("claude-sonnet-4-5")
                .maxTokens(200)
                .addUserMessage(prompt)
                .build()
        );

        String text = response.content().stream()
            .filter(b -> b.type() == ContentBlock.Type.TEXT)
            .map(b -> b.asText().text())
            .findFirst().orElse("");

        return Arrays.stream(text.split(","))
            .map(String::trim)
            .filter(s -> !s.isBlank())
            .toList();
    }

    private String buildPrompt(String trackName, List<Talk> talks) {
        StringBuilder sb = new StringBuilder();
        sb.append("Analyze these conference talks and suggest the optimal order for educational flow.\n");
        sb.append("Return ONLY a comma-separated list of talk IDs in optimal order.\n\n");
        sb.append("Track: ").append(trackName).append("\n\nTalks:\n");
        for (Talk t : talks) {
            sb.append("ID: ").append(t.getId()).append("\n");
            sb.append("Title: ").append(t.getTitle()).append("\n");
            sb.append("Level: ").append(t.getAudienceLevel()).append("\n");
            sb.append("Summary: ").append(t.getSummary()).append("\n\n");
        }
        return sb.toString();
    }
}
```

### Batch Processing (All Tracks in One API Call)

For efficiency, analyze all tracks in a single prompt:

```
Analyze these conference tracks and suggest optimal talk order for each.
Return each track on its own line: TrackName: id1,id2,id3

Track 1: Development Practices
- 4367: BDD intro (BEGINNER)
- 5259: Estimates critique (BEGINNER)
- 1411: ArchUnit testing (BEGINNER)
- 4914: Monorepos (BEGINNER)

Track 2: Java
- 4945: Performance toolbox (BEGINNER)
- 4931: Modern Java features (INTERMEDIATE)
...
```

Parse the response:

```java
Map<String, List<String>> flowOrders = new HashMap<>();
for (String line : response.split("\n")) {
    if (line.contains(":")) {
        String[] parts = line.split(":", 2);
        String track = parts[0].trim();
        List<String> ids = Arrays.stream(parts[1].split(","))
            .map(String::trim).filter(s -> !s.isBlank()).toList();
        flowOrders.put(track, ids);
    }
}
```

## Example Flow Rationale

For the Java track, AI might reason:

1. **4945 (Performance Toolbox)** — Foundational JDK tools knowledge
2. **4931 (Modern Java)** — New language features build on basics
3. **4929 (Design Patterns)** — Apply modern features to patterns
4. **5456 (Java Projects)** — Future of Java, broader perspective
5. **5261 (Loom)** — Advanced concurrency deep-dive

This creates a learning journey: tools → features → patterns → vision → deep-dive.

## Caching Recommendations

Cache AI-generated flow orders to avoid repeated API calls. Regenerate only when talks are added or removed from a track.

```json
{
  "generatedAt": "2025-03-07T10:30:00Z",
  "model": "claude-sonnet-4-5",
  "tracks": {
    "Java": ["4945", "4931", "4929", "5456", "5261"],
    "Security": ["5298", "5268"]
  }
}
```
