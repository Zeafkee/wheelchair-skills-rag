# Unity Integration Guide

This guide explains how to connect your Unity simulation to the RAG backend.

## Flow

1) Unity compiles context (skill being trained, environment, slope, surface) and any telemetry summary (e.g., rear tip warnings).
2) Unity calls `POST /ask` with the user's question and optional filters (e.g., `{ "level": "intermediate", "skill_id": "intermediate-popping-casters" }`).
3) Backend returns step-by-step guidance, safety cues, and success criteria based on retrieved KB chunks.
4) Unity renders instructions (voice/text) and monitors telemetry to display warnings.

## Endpoint

- `POST /ask`
  - body:
    - `question` (string): user query
    - `filters` (object, optional): e.g., `{ "level": "intermediate", "skill_id": "intermediate-popping-casters" }`
  - returns:
    - `answer` (string): guided instructions
    - `citations` (array): KB chunk IDs and titles
    - `used_filters` (object)

Add a second endpoint later for performance analysis (mapping telemetry to KB errors/corrections), e.g., `/score`. Start simple using the telemetry schema.

## Telemetry Mapping (suggested heuristics)

- Rear tip warning + backward wheeling:
  - Error: leaning back while reversing.
  - Correction: lean slightly forward, shorten strokes.
- Ramp descent speed spikes:
  - Error: not sliding rims.
  - Correction: continuous rim slide at ~1 o’clock; add gloves.
- Side slope drift:
  - Error: insufficient uphill lean.
  - Correction: lean uphill/back slightly; short, strong strokes lower hand.
- Caster pops over-rotation:
  - Error: over-powering or late lean-forward on landing.
  - Correction: reduce push amplitude, cue “soft elbows” and earlier forward lean.

## UI Suggestions

- Display dynamic “hand clock” and “lean arrow” indicators.
- Haptics/sounds on safety triggers (tip warnings, collisions).
- Progress bar tied to success criteria (e.g., stable cadence, drift under threshold).

## Next Steps

- Implement `/score` for real-time warnings.
- Persist session metrics and generate adaptive plans from `data/training_plan_template.json`.