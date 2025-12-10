# rag_practice_service.py
import re
import json
from pathlib import Path

# ✅ GERÇEK skill_steps dizini (data/skill_steps)
SKILL_DIR = Path(__file__).resolve().parents[1] / "data" / "skill_steps"


def extract_numbered_steps(answer: str):
    """
    RAG cevabından numaralı step'leri çıkarır.
    """
    pattern = re.compile(
        r"\n(\d+)\.\s+\*\*(.*?)\*\*:\s*(.*?)\n\s*-\s+\*\*Cue\*\*:\s*(.*?)\n",
        re.DOTALL
    )

    steps = []
    for num, title, desc, cue in pattern.findall(answer):
        steps.append({
            "step_number": int(num),
            "title": title.strip(),
            "instruction": desc.strip(),
            "cue": cue.strip()
        })
    return steps


def load_skill_json(skill_id: str):
    """
    Skill JSON'unu data/skill_steps içinden yükler.
    """
    path = SKILL_DIR / f"{skill_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Skill JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def map_steps_to_skill(rag_steps, skill_json):
    """
    HYBRID STRATEGY:
    1) step_number birebir eşleşirse onu kullan
    2) Hiçbir step eşleşmezse -> sıraya göre eşle
    """

    skill_steps = skill_json.get("steps", [])
    skill_step_map = {s["step_number"]: s for s in skill_steps}

    final_steps = []

    # 1️⃣ Önce birebir step_number dene
    for rag_step in rag_steps:
        sn = rag_step["step_number"]
        if sn in skill_step_map:
            skill_step = skill_step_map[sn]
            input_actions = skill_step.get("input_actions", [])
            if input_actions:
                final_steps.append({
                    "step_number": sn,
                    "text": rag_step["instruction"],
                    "cue": rag_step.get("cue"),
                    "expected_actions": [ia["action"] for ia in input_actions]
                })

    # 2️⃣ Eğer HİÇ eşleşme yoksa → sıraya göre eşle
    if not final_steps:
        for i, skill_step in enumerate(skill_steps):
            if i >= len(rag_steps):
                break

            input_actions = skill_step.get("input_actions", [])
            if not input_actions:
                continue

            final_steps.append({
                "step_number": skill_step["step_number"],
                "text": skill_step.get("instruction"),
                "cue": skill_step.get("cue"),
                "expected_actions": [ia["action"] for ia in input_actions]
            })

    return final_steps
