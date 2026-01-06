# https://github.com/Zeafkee/wheelchair-skills-rag/blob/main/scripts/test_suite_helper.py
"""
Helper utilities to load the local test suite (data/test_suites/32_skill_tests.json),
score entries against a question and convert instructions -> numbered steps.

Add this file to scripts/ directory.
"""
import os
import json
import re
from typing import Optional, List, Dict

TEST_SUITE_PATH = os.path.join("data", "test_suites", "32_skill_tests.json")

def load_test_suite(path: str = TEST_SUITE_PATH) -> List[Dict]:
    """Load the test suite JSON (list or dict-with-skills)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # accepted: top-level list, or {"skills": [...]}
        if "skills" in data and isinstance(data["skills"], list):
            return data["skills"]
        # fallback single dict as one entry
        return [data]
    return []

def score_skill_for_query(skill: Dict, query: str) -> int:
    """
    Heuristic scorer:
      - strong boosts for curb/step-related mapped_skill_id tokens
      - counts token matches in label + instructions
      - penalizes helper-required tests unless user mentions helper
    """
    q = (query or "").lower()
    score = 0

    # curb / step tokens give initial signal if present in query
    curb_tokens = ["kaldırım", "curb", "step", "kadem", "yükseklik", "yukarı", "aşağı", "down", "up", "descent", "climb"]
    for t in curb_tokens:
        if t in q:
            score += 4

    # mapped skill id boost (strong signal)
    mapped = (skill.get("mapped_skill_id") or "").lower()
    if mapped:
        # give large boost if mapped indicates curb/advanced-curb etc.
        if "curb" in mapped or "curb-down" in mapped or "curb-up" in mapped:
            score += 30
        # small boost for token overlaps
        for token in re.findall(r"\w+", q):
            if token and token in mapped:
                score += 8

    # text matching in label and instructions (each match * small weight)
    txt = " ".join(filter(None, [
        skill.get("label") or "",
        skill.get("title") or "",
        " ".join(skill.get("instructions") or [])
    ])).lower()

    for token in set(re.findall(r"\w+", q)):
        if token:
            score += txt.count(token) * 2

    # helpers: penalize tests that require helpers unless user asked for help
    if skill.get("requires_helpers"):
        if any(w in q for w in ("yardım", "yardımcı", "helper", "helpers")):
            score += 3
        else:
            score -= 6

    # final small normalization: if no match tokens at all, score may be 0
    return score

def find_best_tests(query: str, top_n: int = 1, path: str = TEST_SUITE_PATH) -> List[Dict]:
    """Return top_n test entries from the test suite ranked by score (only scores>0)."""
    tests = load_test_suite(path)
    scored = []
    for t in tests:
        sc = score_skill_for_query(t, query)
        scored.append((sc, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [t for sc, t in scored if sc > 0][:top_n]
    return results

def normalize_instructions_to_steps(test_entry: Dict) -> List[Dict]:
    """
    Convert test_entry.instructions (list[str]) -> list of normalized step dicts:
    { step_number, text, title, cue, expected_actions }
    """
    instrs = test_entry.get("instructions") or []
    steps = []
    for i, ins in enumerate(instrs, start=1):
        steps.append({
            "step_number": i,
            "text": ins,
            "title": None,
            "cue": None,
            "expected_actions": []
        })
    return steps