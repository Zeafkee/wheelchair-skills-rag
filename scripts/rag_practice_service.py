# rag_practice_service.py (Updated: Solo-only, Multi-action Step Splitting, Negation check)
import re
import json
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TEST_SUITES_FILE = DATA_DIR / "test_suites" / "32_skill_tests.json"

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


def map_steps_to_skill(rag_steps, skill_json):
    """
    Maps RAG steps to filtered actionable solo steps.
    If multiple actions are found in one RAG step, it splits them into separate Unity steps.
    """
    final_steps = []
    
    for i, rag_step in enumerate(rag_steps):
        instruction = rag_step.get("instruction", "")
        
        # 1. Filter out Helper/Assistant/Spotter steps
        if any(k in instruction.lower() for k in ["helper", "assistant", "spotter"]):
            continue
            
        # 2. Generate actions (can be multiple)
        expected_actions = generate_expected_actions(instruction)
        
        if not expected_actions:
            continue
        
        cue_val = rag_step.get("cue")
        
        # 3. Split multiple actions into separate steps
        # Use a specific order for splitting to ensure logic (e.g. Lean before Move)
        # We'll use a simple priority order for the split sequence
        priority = ["pop_casters", "move_forward", "move_backward", "turn_left", "turn_right", "brake"]
        
        sorted_actions = sorted(expected_actions, key=lambda x: priority.index(x) if x in priority else 99)

        for action in sorted_actions:
            final_steps.append({
                "step_number": len(final_steps) + 1,
                "text": instruction,
                "cue": cue_val,
                "expected_actions": [action] # Always one action per step now
            })

    return final_steps