# AI-Powered Educational Flow Analysis

This guide explains how to use AI/LLM to analyze talk summaries and determine optimal educational flow.

## Overview

The educational flow constraint ensures talks within a track are ordered for optimal learning. While audience level (beginner → advanced) provides a baseline, analyzing talk summaries with AI enables more nuanced ordering.

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

### 4. Apply to Solver

```java
Map<String, List<String>> flowOrders = new HashMap<>();
flowOrders.put("Development Practices", List.of("4367", "5259", "1411", "4914"));
flowOrders.put("Java", List.of("4945", "4931", "4929", "5456", "5261"));
// ... more tracks

CsvDataReader reader = new CsvDataReader();
reader.applyFlowOrder(talks, flowOrders);
```

## Integration with Claude

### Using Claude API

```java
import com.anthropic.client.AnthropicClient;

public class FlowAnalyzer {
    private final AnthropicClient client;
    
    public List<String> analyzeTrackFlow(String trackName, List<Talk> talks) {
        String prompt = buildPrompt(trackName, talks);
        
        var response = client.messages().create(
            MessageCreateParams.builder()
                .model("claude-sonnet-4-20250514")
                .maxTokens(100)
                .addMessage(MessageParam.user(prompt))
                .build()
        );
        
        return parseResponse(response.content().get(0).text());
    }
}
```

### Batch Processing

For efficiency, analyze all tracks in one prompt:

```
Analyze these conference tracks and suggest optimal talk order for each.

Track 1: Development Practices
- 4367: BDD intro (BEGINNER)
- 5259: Estimates critique (BEGINNER)
- 1411: ArchUnit testing (BEGINNER)
- 4914: Monorepos (BEGINNER)

Track 2: Java
- 4945: Performance toolbox (BEGINNER)
- 4931: Modern Java features (INTERMEDIATE)
...

Return as:
Development Practices: id1,id2,id3,id4
Java: id1,id2,id3,id4,id5
```

## Example Flow Rationale

For the Java track, AI might reason:

1. **4945 (Performance Toolbox)** - Foundational JDK tools knowledge
2. **4931 (Modern Java)** - New language features build on basics
3. **4929 (Design Patterns)** - Apply modern features to patterns
4. **5456 (Java Projects)** - Future of Java, broader perspective
5. **5261 (Loom)** - Advanced implementation patterns

This creates a learning journey from tools → features → patterns → vision → deep-dive.

## Caching Recommendations

Cache AI-generated flow orders to avoid repeated API calls:

```java
// Store as JSON
{
  "generatedAt": "2024-01-15T10:30:00Z",
  "model": "claude-sonnet-4-20250514",
  "tracks": {
    "Java": ["4945", "4931", "4929", "5456", "5261"],
    "Security": ["5298", "5268"]
  }
}
```

Regenerate only when talks are added/removed from a track.
