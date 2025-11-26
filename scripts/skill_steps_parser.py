"""
Skill Steps Parser
==================
Bu modül, data/skills.jsonl dosyasındaki becerileri okuyup
adımlara (steps) dönüştürür ve beklenen input sequence'larını tanımlar.
"""

import json
import os
from typing import Optional

# Unity input mapping dosyası
INPUT_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "unity_input_mapping.json")
SKILLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "skills.jsonl")
SKILL_STEPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "skill_steps")

# Adım instruction'larına göre beklenen input mapping
# Bu mapping, adım talimatlarındaki anahtar kelimelere göre input'ları belirler
INSTRUCTION_TO_INPUT_MAP = {
    # İleri hareket
    "forward": ["W"],
    "ileri": ["W"],
    "approach": ["W"],
    "yaklaş": ["W"],
    "push": ["W"],
    "it": ["W"],
    "momentum": ["W"],
    
    # Geri hareket
    "backward": ["S"],
    "geri": ["S"],
    "back up": ["S"],
    "back": ["S"],
    
    # Sola dön
    "turn left": ["A"],
    "sola": ["A"],
    "left turn": ["A"],
    
    # Sağa dön
    "turn right": ["D"],
    "sağa": ["D"],
    "right turn": ["D"],
    
    # Dön (genel)
    "turn": ["A", "D"],  # Yön belirtilmemişse her iki yön olabilir
    "pivot": ["A", "D"],
    
    # Caster pop
    "pop casters": ["X"],
    "caster": ["X"],
    "casters up": ["X"],
    "tip casters": ["X"],
    "pop": ["X"],
    
    # Öne eğil
    "lean forward": ["V"],
    "öne eğil": ["V"],
    "chest toward": ["V"],
    
    # Arkaya eğil
    "lean back": ["B"],
    "arkaya eğil": ["B"],
    
    # Fren / Dur
    "stop": ["SPACE"],
    "dur": ["SPACE"],
    "brake": ["SPACE"],
    "fren": ["SPACE"],
    "stabilize": ["SPACE"],
    
    # Sol tekerlek
    "left wheel": ["Q"],
    "left rim": ["Q"],
    
    # Sağ tekerlek
    "right wheel": ["E"],
    "right rim": ["E"],
    
    # Denge
    "balance": ["C"],
    "denge": ["C"],
    "center": ["C"],
    
    # Wheelie
    "wheelie": ["X", "B"],  # Pop + lean back
    "rock": ["V", "B"],  # Öne-arkaya sallanma
}

# Hata mapping - yanlış yapılabilecek hatalar
COMMON_ERROR_INPUTS = {
    "pop_casters": {
        "wrong_inputs": ["W", "S", "V"],
        "error_descriptions": {
            "W": "Ön tekerlekleri kaldırmak yerine ileri gitmeye çalıştı",
            "S": "Ön tekerlekleri kaldırmak yerine geri gitmeye çalıştı",
            "V": "Ön tekerlekleri kaldırmak yerine öne eğildi"
        }
    },
    "move_forward": {
        "wrong_inputs": ["S", "SPACE", "X"],
        "error_descriptions": {
            "S": "İleri gitmek yerine geri gitti",
            "SPACE": "İleri gitmek yerine frene bastı",
            "X": "İleri gitmek yerine caster kaldırdı"
        }
    },
    "brake": {
        "wrong_inputs": ["W", "S"],
        "error_descriptions": {
            "W": "Durmak yerine ileri gitti",
            "S": "Durmak yerine geri gitti"
        }
    },
    "lean_forward": {
        "wrong_inputs": ["B", "W"],
        "error_descriptions": {
            "B": "Öne eğilmek yerine arkaya eğildi",
            "W": "Öne eğilmek yerine ileri gitti"
        }
    },
    "lean_backward": {
        "wrong_inputs": ["V", "S"],
        "error_descriptions": {
            "V": "Arkaya eğilmek yerine öne eğildi",
            "S": "Arkaya eğilmek yerine geri gitti"
        }
    }
}


def load_input_mapping() -> dict:
    """Unity input mapping'i yükle"""
    with open(INPUT_MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_skills() -> list[dict]:
    """Skills.jsonl dosyasından tüm becerileri yükle"""
    skills = []
    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                skills.append(json.loads(line))
    return skills


def extract_expected_inputs(instruction: str) -> list[str]:
    """
    Adım talimatından beklenen input'ları çıkar
    """
    instruction_lower = instruction.lower()
    inputs = []
    
    # Öncelik sırasına göre kontrol et
    for keyword, expected_inputs in INSTRUCTION_TO_INPUT_MAP.items():
        if keyword in instruction_lower:
            for inp in expected_inputs:
                if inp not in inputs:
                    inputs.append(inp)
    
    return inputs if inputs else ["W"]  # Varsayılan olarak ileri


def get_possible_errors(expected_inputs: list[str], input_mapping: dict) -> list[dict]:
    """
    Beklenen input'lara göre olası hataları döndür
    """
    errors = []
    
    for expected_input in expected_inputs:
        action = input_mapping.get(expected_input, {}).get("action", "")
        
        if action in COMMON_ERROR_INPUTS:
            error_info = COMMON_ERROR_INPUTS[action]
            for wrong_input in error_info["wrong_inputs"]:
                wrong_action = input_mapping.get(wrong_input, {}).get("action", "unknown")
                errors.append({
                    "expected_input": expected_input,
                    "expected_action": action,
                    "wrong_input": wrong_input,
                    "wrong_action": wrong_action,
                    "error_type": "wrong_input",
                    "description": error_info["error_descriptions"].get(wrong_input, "Yanlış tuşa basıldı")
                })
    
    return errors


def parse_skill_steps(skill: dict, input_mapping: dict) -> dict:
    """
    Tek bir beceriyi parse edip adım detaylarını döndür
    """
    skill_id = skill.get("id", "")
    title = skill.get("title", "")
    level = skill.get("level", "")
    structured = skill.get("structured", {})
    steps = structured.get("steps", [])
    
    parsed_steps = []
    
    for step in steps:
        step_number = step.get("n", 0)
        instruction = step.get("instruction", "")
        cues = step.get("cues", [])
        
        # Beklenen input'ları çıkar
        expected_inputs = extract_expected_inputs(instruction)
        
        # Her input için action bilgisini al
        input_actions = []
        for inp in expected_inputs:
            action_info = input_mapping.get(inp, {})
            input_actions.append({
                "key": inp,
                "action": action_info.get("action", "unknown"),
                "description": action_info.get("description", "")
            })
        
        # Olası hataları belirle
        possible_errors = get_possible_errors(expected_inputs, input_mapping)
        
        parsed_step = {
            "step_number": step_number,
            "instruction": instruction,
            "cues": cues,
            "expected_inputs": expected_inputs,
            "input_actions": input_actions,
            "possible_errors": possible_errors
        }
        
        parsed_steps.append(parsed_step)
    
    return {
        "skill_id": skill_id,
        "title": title,
        "level": level,
        "total_steps": len(parsed_steps),
        "common_errors": structured.get("common_errors", []),
        "corrections": structured.get("corrections", []),
        "steps": parsed_steps
    }


def parse_all_skills() -> list[dict]:
    """
    Tüm becerileri parse et
    """
    input_mapping = load_input_mapping()
    skills = load_skills()
    
    parsed_skills = []
    
    for skill in skills:
        # Sadece 'skill' tipindeki kayıtları işle
        if skill.get("type") == "skill":
            parsed = parse_skill_steps(skill, input_mapping)
            parsed_skills.append(parsed)
    
    return parsed_skills


def save_parsed_skills(parsed_skills: list[dict]) -> None:
    """
    Parse edilmiş becerileri ayrı dosyalara kaydet
    """
    os.makedirs(SKILL_STEPS_DIR, exist_ok=True)
    
    for skill in parsed_skills:
        skill_id = skill.get("skill_id", "unknown")
        filepath = os.path.join(SKILL_STEPS_DIR, f"{skill_id}.json")
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
    
    # Tüm becerilerin özet listesini de kaydet
    summary_path = os.path.join(SKILL_STEPS_DIR, "_index.json")
    summary = [
        {
            "skill_id": s["skill_id"],
            "title": s["title"],
            "level": s["level"],
            "total_steps": s["total_steps"]
        }
        for s in parsed_skills
    ]
    
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def get_skill_steps(skill_id: str) -> Optional[dict]:
    """
    Belirli bir becerinin adımlarını yükle
    """
    filepath = os.path.join(SKILL_STEPS_DIR, f"{skill_id}.json")
    
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return None


def main():
    """Ana fonksiyon - tüm becerileri parse et ve kaydet"""
    print("Beceriler parse ediliyor...")
    
    parsed_skills = parse_all_skills()
    
    print(f"Toplam {len(parsed_skills)} beceri parse edildi.")
    
    save_parsed_skills(parsed_skills)
    
    print(f"Dosyalar kaydedildi: {SKILL_STEPS_DIR}")
    
    # Örnek çıktı
    for skill in parsed_skills[:3]:
        print(f"\n--- {skill['title']} ({skill['skill_id']}) ---")
        print(f"Seviye: {skill['level']}")
        print(f"Toplam adım: {skill['total_steps']}")
        for step in skill["steps"][:2]:
            print(f"  Adım {step['step_number']}: {step['instruction'][:50]}...")
            print(f"    Beklenen input'lar: {step['expected_inputs']}")


if __name__ == "__main__":
    main()
