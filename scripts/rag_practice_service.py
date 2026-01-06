# rag_practice_service.py (Updated: GPT-based action generation)
import re
import json
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Paths
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TEST_SUITES_FILE = DATA_DIR / "test_suites" / "32_skill_tests.json"

# OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=OPENAI_API_KEY)

# Available actions in the wheelchair simulator
AVAILABLE_ACTIONS = [
    "move_forward",   # W key
    "move_backward",  # S key
    "turn_left",      # A key
    "turn_right",     # D key
    "brake",          # SPACE key
    "pop_casters"     # X key
]

def clean_rag_text(text: str):
    """
    Cleans RAG text: removes markdown, extracts inline cues.
    """
    if not text:
        return {"title": None, "instruction": "", "cue": None}

    t = text
    # Remove bold/italic markers
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = t.strip()

    # Extract inline cue
    cue = None
    cue_match = re.search(r'[\s,\.\-]+(?:Cues?|İpucu|İpuçları)\s*[:\-]?\s*(.*)$', t, re.I)
    if cue_match:
        cue = cue_match.group(1).strip()
        t = t[:cue_match.start()].strip()
    else:
        cue_match = re.search(r'[\s,\.\-]+(?:Cues?|İpucu|İpuçları)\s*$', t, re.I)
        if cue_match:
             t = t[:cue_match.start()].strip()

    return {"title": None, "instruction": t, "cue": cue}


def extract_numbered_steps(answer: str):
    """
    Extracts numbered steps from RAG answer.
    """
    steps = []
    cur = None

    if not answer:
        return steps

    for line in answer.splitlines():
        line = line.strip()
        if not line: continue
        
        m = re.match(r'^\s*(?:Step\s+)?(\d+)[\.\)]\s*(.*)', line, re.I)
        if m:
            if cur:
                cleaned = clean_rag_text(cur["instruction"])
                steps.append({
                    "step_number": cur["step_number"],
                    "instruction": cleaned.get("instruction"),
                    "cue": cur.get("cue") or cleaned.get("cue")
                })
            cur = {
                "step_number": int(m.group(1)),
                "instruction": m.group(2).strip() or ""
            }
            continue

        if cur:
            cur["instruction"] += " " + line

    if cur:
        cleaned = clean_rag_text(cur["instruction"])
        steps.append({
            "step_number": cur["step_number"],
            "instruction": cleaned.get("instruction"),
            "cue": cur.get("cue") or cleaned.get("cue")
        })

    return steps


def load_skill_from_test_suite(skill_id_or_mapped_id: str):
    """
    Loads skill definition from 32_skill_tests.json.
    """
    if not TEST_SUITES_FILE.exists():
        return None
    
    try:
        data = json.loads(TEST_SUITES_FILE.read_text(encoding="utf-8"))
        for item in data:
            if item.get("test_id") == skill_id_or_mapped_id or item.get("mapped_skill_id") == skill_id_or_mapped_id:
                return item
    except:
        pass
    return None

def generate_expected_actions(instruction: str):
    """
    Identifies all relevant actions. Splitting happens in map_steps_to_skill.
    """
    text = instruction.lower()
    
    def has_active_keyword(keywords):
        for k in keywords:
            pattern = rf'(?<!avoiding )(?<!avoid )(?<!don\'t )(?<!no )(?<!without ){re.escape(k)}'
            if re.search(pattern, text):
                return True
        return False

    all_found = []

    if has_active_keyword(["forward", "push", "approach", "roll", "drive", "cover", "sit up", "alignment", "square", "up", "platform"]):
        all_found.append("move_forward")
    
    if has_active_keyword(["backward", "back", "reverse", "below"]):
        all_found.append("move_backward")
        
    if has_active_keyword(["left"]):
        all_found.append("turn_left")
        
    if has_active_keyword(["right"]):
        all_found.append("turn_right")
            
    if has_active_keyword(["pop", "caster", "lift", "climb", "clearance", "snag", "high", "height"]):
        all_found.append("pop_casters")
        
    if has_active_keyword(["brake", "stop", "hold", "stabilize", "balance", "control", "wait", "stay"]):
        all_found.append("brake")

    # Clean up conflicting movement from "back up"
    if "back up" in text or "back to" in text:
        if "move_forward" in all_found: all_found.remove("move_forward")
        if "move_backward" not in all_found: all_found.append("move_backward")

    return list(set(all_found))


def generate_actions_with_gpt(steps: list[dict]) -> list[dict]:
    """
    Uses GPT to analyze steps and generate accurate expected_actions.
    Returns steps with expected_actions assigned, filtering out helper/spotter steps.
    """
    if not steps:
        return []
    
    # Build the prompt for GPT
    steps_text = "\n".join([
        f"{i+1}. {step.get('instruction', '')}"
        for i, step in enumerate(steps)
    ])
    
    prompt = f"""You are analyzing wheelchair skill training steps. For each step below, determine the expected wheelchair action(s).

Available actions:
- move_forward (W key): Moving forward/approaching/pushing ahead
- move_backward (S key): Moving backward/reversing/backing up
- turn_left (A key): Turning left
- turn_right (D key): Turning right  
- brake (SPACE key): Stopping/holding position/stabilizing/waiting
- pop_casters (X key): Lifting front casters/popping wheelie

Steps to analyze:
{steps_text}

Rules:
1. Assign ONE action per step whenever possible
2. If a step describes "left OR right" (user can choose either), return BOTH actions: ["turn_left", "turn_right"]
3. If a step requires SEQUENTIAL actions (e.g., "pop casters THEN move forward"), split into 2 steps with different instruction texts
4. Filter out steps for helpers/spotters/assistants - do NOT include them
5. Focus on solo wheelchair user actions only
6. For positioning/alignment steps, use "brake" to hold position
7. Words like "upright", "sit up", "square" are about posture, NOT forward movement - use "brake" unless explicitly moving

Return a JSON object with this exact format:
{{
  "steps": [
    {{
      "step_number": 1,
      "instruction": "exact instruction text from original step",
      "expected_actions": ["action_name"],
      "cue": "any helpful cue or tip"
    }}
  ]
}}

For steps requiring sequential actions, create separate entries with modified instruction text that clearly describes each action.
Example: "Pop casters and move forward" → 
  Step 1: "Pop casters" with ["pop_casters"]
  Step 2: "Move forward" with ["move_forward"]

Return only the JSON, no other text."""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a wheelchair training expert analyzing skill steps to assign correct actions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        gpt_steps = result.get("steps", [])
        
        # Merge cues from original steps
        final_steps = []
        for gpt_step in gpt_steps:
            # Try to find matching original step by instruction similarity
            original_cue = None
            for orig_step in steps:
                if orig_step.get("instruction", "").strip() in gpt_step.get("instruction", ""):
                    original_cue = orig_step.get("cue")
                    break
            
            final_steps.append({
                "step_number": gpt_step.get("step_number"),
                "instruction": gpt_step.get("instruction", ""),
                "expected_actions": gpt_step.get("expected_actions", []),
                "cue": gpt_step.get("cue") or original_cue
            })
        
        return final_steps
        
    except Exception as e:
        print(f"Error in generate_actions_with_gpt: {e}")
        # Fallback to empty list if GPT fails
        return []


def map_steps_to_skill(rag_steps, skill_json):
    """
    Maps RAG steps to filtered actionable solo steps using GPT-based action generation.
    """
    # Use GPT to analyze and assign actions to all steps at once
    gpt_steps = generate_actions_with_gpt(rag_steps)
    
    # Convert to Unity format
    final_steps = []
    for step in gpt_steps:
        final_steps.append({
            "step_number": len(final_steps) + 1,
            "text": step.get("instruction", ""),
            "cue": step.get("cue"),
            "expected_actions": step.get("expected_actions", [])
        })
    
    return final_steps