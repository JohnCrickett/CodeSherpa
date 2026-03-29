# Task 15: Unified Query Classification

## Objective
Replace the current split classification (exact-match for "map", regex for follow-ups, LLM for exploration/specific) with a single LLM call that classifies all four query types, using conversation history as context.

## Requirements Covered
- REQ-CLASS-01, REQ-CLASS-02, REQ-CLASS-03

## Acceptance Criteria

### Single-Call Classification
- `classify_query()` makes one LLM call that returns one of: `map`, `follow_up`, `exploration`, `specific`
- The classification prompt includes the conversation history (last 3 entries) when present
- The `_FOLLOW_UP_INDICATORS` regex is removed; follow-up detection is handled entirely by the LLM
- The hardcoded `query.lower() == "map"` check is removed; the LLM determines map intent (e.g. "show me the map", "give me an overview of the structure" should also classify as map)

### Routing Preserved
- `route_by_type()` and the LangGraph conditional edges remain unchanged
- The four handler nodes (handle_map, plan_exploration, multi_step_retrieve, update_memory) are not modified

### Tests
- Test that "map" classifies as `map`
- Test that "show me the project structure" classifies as `map`
- Test that "what calls this function?" with conversation history classifies as `follow_up`
- Test that "how does authentication work?" classifies as `exploration`
- Test that "what does parse_codebase do?" classifies as `specific`
- Test that classification without conversation history never returns `follow_up`
