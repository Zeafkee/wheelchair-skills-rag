# RAG vs No-RAG Performance Analysis
**Date:** 2026-01-07
**Subject:** Analysis of Lower RAG Performance in Wheelchair Skills Test

## 1. Executive Summary

A comparison test between RAG (Retrieval-Augmented Generation) and No-RAG approaches using GPT-5-mini and Gemini-3-Flash revealed that **No-RAG models outperformed RAG models by approximately 6%**.

*   **No-RAG Average:** 78.4%
*   **RAG Average:** 72.4%

The primary reason for this discrepancy is a mismatch between the **nuanced, physical instructions** retrieved by the RAG system (designed for real-world humans) and the **discrete, rigid input actions** expected by the simulation test suite. No-RAG models, relying on general knowledge, tended to generate generic "video game" logic (e.g., "Turn Left, then Turn Right") which coincidentally aligned better with the test suite's requirements than the highly specific physical descriptions retrieved by RAG.

## 2. Detailed Failure Analysis

The analysis of `rag_comparison_4models_20260107_160702.txt` and the system architecture reveals specific patterns of failure:

### 2.1. The "Analog vs. Digital" Mapping Problem
*   **Scenario:** Skill #19 (Rolls across side-slope 5deg)
*   **RAG Behavior:** Retrieved text advises to "Apply more force to the rim on the downhill side". The action mapper interpreted this physically accurate description as `move_forward` (pushing).
*   **Test Expectation:** The test suite expects explicit steering commands: `turn_left` or `turn_right` to counteract the slope.
*   **Result:** RAG failed because "push harder" was not translated to "turn", whereas No-RAG models explicitly guessed "Turn left to steer uphill".

### 2.2. Missing "Game-isms"
*   **Scenario:** Skill #6 (Maneuvers sideways 0.5m)
*   **RAG Behavior:** Retrieved text described "alternating strokes" (`move_forward`, `move_backward`) to inch sideways.
*   **Test Expectation:** The simulation likely requires explicit rotation inputs (`turn_left`, `turn_right`) combined with movement to achieve lateral displacement (parallel park maneuver).
*   **Result:** RAG provided the correct *physical* technique for a real wheelchair, but the simulation required specific *steering* inputs that weren't explicitly named in the retrieved text.

### 2.3. Over-Specificity vs. Sequence
*   **Scenario:** Skill #4 (Turns while moving backwards 90deg)
*   **RAG Behavior:** Retrieved text focused on "Initiate turn... Control rate". The action mapper found `turn_left` but missed `turn_right` (often needed for straightening out).
*   **Test Expectation:** `move_backward, turn_left, turn_right`.
*   **Result:** No-RAG models, simply guessing a full maneuver, were more likely to include the "straighten out" action (`turn_right`) than the RAG model which strictly followed the retrieved text that might have implied it but didn't explicitly say "turn right".

## 3. Root Cause

1.  **Content Mismatch:** The content in `data/skills.jsonl` is written for **real-world human biomechanics** (e.g., "hands at 11 o'clock", "lean forward"). It is not written for a keyboard-controlled simulation.
2.  **Strict Action Mapping:** The `rag_practice_service.py` uses an LLM to map text to actions. It is instructed to map "Turn" to `turn_left/right`. It is *not* sufficiently instructed to infer that "Push harder on left" *means* `turn_right` in the context of the simulation.
3.  **Test Suite Rigidity:** The test suite checks for the presence of specific keys. If the RAG model describes the correct *physics* but fails to trigger the specific *key keyword*, it fails.

## 4. Recommendations

### 4.1. Short-Term Fix (Prompt Engineering)
Update the `generate_actions_with_gpt` prompt in `rag_practice_service.py` to handle implicit steering:
*   **Instruction:** "If the text describes applying uneven force, pushing harder on one side, or steering/correcting heading, map this to the appropriate `turn_left` or `turn_right` action."
*   **Instruction:** "If a maneuver involves changing position sideways or aligning, assume steering (`turn_left/right`) is required along with movement."

### 4.2. Long-Term Fix (Content Augmentation)
Add a "simulation_cues" field to `data/skills.jsonl` that explicitly translates physical moves to game inputs.
*   *Current:* "Apply more force to the downhill wheel."
*   *Augmented:* "Apply more force to the downhill wheel (Simulation: Input `turn_left` to counter-steer)."

### 4.3. Conclusion
The RAG system is actually "smarter" and more physically accurate, but it is being penalized for not speaking the "game language." The No-RAG models are succeeding by "gaming the system" with generic inputs. Improving the Action Mapping layer will allow the RAG system's superior physical knowledge to be correctly translated into simulation success.
