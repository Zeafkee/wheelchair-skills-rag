"""
Test Data Generator for User Progress
Generates realistic wheelchair skills training data
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

# Skill tanımları
SKILLS = {
    "a01_10m_forward": {
        "name": "Rolls forwards 10m",
        "steps": [
            {"step":  1, "action": "move_forward"},
            {"step": 2, "action": "move_forward"},
            {"step": 3, "action":  "brake"}
        ],
        "difficulty": "easy",
        "success_rate_base": 0.85
    },
    "a02_2m_backward": {
        "name": "Rolls backwards 2m",
        "steps": [
            {"step":  1, "action": "move_backward"},
            {"step": 2, "action": "move_backward"},
            {"step": 3, "action": "brake"}
        ],
        "difficulty": "easy",
        "success_rate_base": 0.80
    },
    "a03_5m_backward": {
        "name": "Rolls backwards 5m",
        "steps":  [
            {"step": 1, "action": "move_backward"},
            {"step": 2, "action": "move_backward"},
            {"step": 3, "action": "brake"}
        ],
        "difficulty":  "easy",
        "success_rate_base": 0.75
    },
    "a04_turn_backward_90": {
        "name": "Turns while moving backwards 90deg",
        "steps": [
            {"step": 1, "action": "move_backward"},
            {"step": 2, "action": "turn_left"},
            {"step": 3, "action": "move_backward"},
            {"step": 4, "action": "brake"}
        ],
        "difficulty":  "medium",
        "success_rate_base": 0.60
    },
    "a05_turn_in_place_180":  {
        "name": "Turns in place 180deg",
        "steps": [
            {"step": 1, "action": "turn_left"},
            {"step": 2, "action": "turn_left"},
            {"step": 3, "action": "brake"}
        ],
        "difficulty": "medium",
        "success_rate_base": 0.70
    },
    "a06_sideways_maneuver":  {
        "name": "Maneuvers sideways 0.5m",
        "steps": [
            {"step":  1, "action": "turn_right"},
            {"step": 2, "action": "move_forward"},
            {"step": 3, "action": "turn_left"},
            {"step": 4, "action": "move_forward"}
        ],
        "difficulty": "hard",
        "success_rate_base":  0.45
    },
    "a17_ascend_10deg": {
        "name": "Ascends 10deg incline",
        "steps": [
            {"step": 1, "action": "move_forward"},
            {"step": 2, "action": "move_forward"},
            {"step": 3, "action": "brake"}
        ],
        "difficulty": "medium",
        "success_rate_base":  0.65
    },
    "a18_descend_10deg":  {
        "name": "Descends 10deg incline",
        "steps": [
            {"step": 1, "action": "move_forward"},
            {"step": 2, "action": "brake"},
            {"step": 3, "action": "move_forward"},
            {"step":  4, "action": "brake"}
        ],
        "difficulty": "medium",
        "success_rate_base": 0.60
    },
    "a21_gap_15cm": {
        "name": "Gets over gap 15cm",
        "steps":  [
            {"step": 1, "action": "move_forward"},
            {"step": 2, "action": "pop_casters"},
            {"step": 3, "action": "move_forward"},
            {"step": 4, "action": "brake"}
        ],
        "difficulty": "hard",
        "success_rate_base":  0.50
    },
    "a25_curb_up_15cm": {
        "name":  "Ascends curb 15cm",
        "steps": [
            {"step": 1, "action":  "move_forward"},
            {"step":  2, "action": "pop_casters"},
            {"step": 3, "action":  "move_forward"},
            {"step":  4, "action": "move_forward"},
            {"step":  5, "action": "brake"}
        ],
        "difficulty": "hard",
        "success_rate_base":  0.40
    },
    "a26_curb_down_15cm": {
        "name":  "Descends curb 15cm",
        "steps":  [
            {"step": 1, "action": "move_backward"},
            {"step": 2, "action": "pop_casters"},
            {"step": 3, "action": "move_backward"},
            {"step": 4, "action":  "brake"}
        ],
        "difficulty": "hard",
        "success_rate_base": 0.35
    },
    "a27_wheelie_30sec":  {
        "name": "Performs stationary wheelie 30sec",
        "steps": [
            {"step": 1, "action": "move_backward"},
            {"step": 2, "action": "pop_casters"},
            {"step": 3, "action":  "brake"},
            {"step": 4, "action": "brake"}
        ],
        "difficulty": "expert",
        "success_rate_base":  0.25
    },
    "a28_wheelie_turn_180":  {
        "name": "Turns in wheelie position 180deg",
        "steps": [
            {"step":  1, "action": "pop_casters"},
            {"step": 2, "action":  "turn_left"},
            {"step": 3, "action": "turn_left"},
            {"step": 4, "action": "brake"}
        ],
        "difficulty":  "expert",
        "success_rate_base": 0.20
    }
}

# Kullanıcı profilleri
USERS = {
    "user_beginner_01": {"skill_level": 0.3, "name":  "Beginner Ali"},
    "user_beginner_02": {"skill_level": 0.4, "name": "Beginner Ayse"},
    "user_intermediate_01":  {"skill_level":  0.6, "name": "Intermediate Mehmet"},
    "user_intermediate_02": {"skill_level": 0.7, "name": "Intermediate Zeynep"},
    "user_advanced_01": {"skill_level": 0.9, "name": "Advanced Can"}
}

# Yaygın hata türleri
ERROR_TYPES = {
    "wrong_input": 0.4,
    "wrong_direction": 0.25,
    "stopped_instead_of_moving":  0.15,
    "moved_instead_of_stopping": 0.1,
    "missed_pop_casters": 0.1
}

# Action karışıklıkları (hangi action yerine ne yapılıyor)
ACTION_CONFUSIONS = {
    "move_forward":  ["move_backward", "turn_left", "turn_right", "brake"],
    "move_backward": ["move_forward", "turn_left", "turn_right", "brake"],
    "turn_left": ["turn_right", "move_forward"],
    "turn_right": ["turn_left", "move_forward"],
    "brake": ["move_forward", "move_backward"],
    "pop_casters": ["move_forward", "brake", "move_backward"]
}


def get_timestamp(base_time, offset_minutes):
    """ISO 8601 timestamp üret"""
    dt = base_time + timedelta(minutes=offset_minutes)
    return dt.isoformat().replace("+00:00", "Z")


def generate_attempt_id():
    """Benzersiz attempt ID üret"""
    return f"att_{uuid.uuid4().hex[:8]}"


def should_succeed(skill_id, user_skill_level):
    """Kullanıcının bu skill'de başarılı olup olmayacağını belirle"""
    skill = SKILLS[skill_id]
    base_rate = skill["success_rate_base"]
    
    # Kullanıcı seviyesine göre ayarla
    adjusted_rate = base_rate * (0.5 + user_skill_level * 0.5)
    
    return random.random() < adjusted_rate


def get_wrong_action(expected_action):
    """Yanlış action seç"""
    options = ACTION_CONFUSIONS. get(expected_action, ["brake"])
    return random.choice(options)


def get_error_type(expected_action, actual_action):
    """Hata tipini belirle"""
    if expected_action in ["move_forward", "move_backward"] and actual_action == "brake":
        return "stopped_instead_of_moving"
    if expected_action == "brake" and actual_action in ["move_forward", "move_backward"]:
        return "moved_instead_of_stopping"
    if expected_action == "pop_casters" and actual_action != "pop_casters": 
        return "missed_pop_casters"
    if expected_action in ["move_forward", "move_backward"] and actual_action in ["move_forward", "move_backward"]:
        return "wrong_direction"
    return "wrong_input"


def generate_attempt(user_id, skill_id, base_time, attempt_offset):
    """Tek bir attempt üret"""
    user = USERS[user_id]
    skill = SKILLS[skill_id]
    
    attempt_id = generate_attempt_id()
    start_time = get_timestamp(base_time, attempt_offset)
    
    step_inputs = []
    step_errors = []
    success = True
    failed_step = None
    
    # Başarılı olacak mı?
    will_succeed = should_succeed(skill_id, user["skill_level"])
    
    if not will_succeed: 
        # Hangi step'te fail olacak?  (Zor step'lerde daha olası)
        fail_weights = []
        for i, step in enumerate(skill["steps"]):
            # pop_casters ve turn action'ları daha zor
            if step["action"] == "pop_casters":
                fail_weights.append(3)
            elif step["action"] in ["turn_left", "turn_right"]: 
                fail_weights.append(2)
            else: 
                fail_weights. append(1)
        
        total_weight = sum(fail_weights)
        fail_probs = [w / total_weight for w in fail_weights]
        failed_step = random. choices(range(len(skill["steps"])), weights=fail_probs)[0]
    
    current_time_offset = attempt_offset
    
    for i, step in enumerate(skill["steps"]):
        current_time_offset += random.randint(1, 3)  # 1-3 saniye arasında
        
        expected_action = step["action"]
        
        if failed_step is not None and i == failed_step: 
            # Bu step'te hata yap
            actual_action = get_wrong_action(expected_action)
            error_type = get_error_type(expected_action, actual_action)
            
            step_inputs.append({
                "step_number": step["step"],
                "expected_input": expected_action,
                "actual_input":  actual_action,
                "is_correct": False,
                "timestamp": get_timestamp(base_time, current_time_offset)
            })
            
            step_errors. append({
                "step_number": step["step"],
                "error_type":  error_type,
                "expected_action": expected_action,
                "actual_action": actual_action,
                "timestamp": get_timestamp(base_time, current_time_offset)
            })
            
            success = False
            break  # Hata sonrası attempt biter
        else:
            # Doğru yap
            step_inputs.append({
                "step_number": step["step"],
                "expected_input": expected_action,
                "actual_input": expected_action,
                "is_correct":  True,
                "timestamp": get_timestamp(base_time, current_time_offset)
            })
    
    end_time = get_timestamp(base_time, current_time_offset + 1)
    
    return {
        "attempt_id": attempt_id,
        "user_id": user_id,
        "skill_id": skill_id,
        "start_time":  start_time,
        "end_time": end_time,
        "step_inputs": step_inputs,
        "step_errors": step_errors,
        "success": success
    }


def calculate_skill_progress(attempts):
    """Kullanıcının skill progress'ini hesapla"""
    skill_progress = {}
    
    for attempt in attempts:
        skill_id = attempt["skill_id"]
        
        if skill_id not in skill_progress:
            skill_progress[skill_id] = {
                "skill_id": skill_id,
                "attempts":  0,
                "successful_attempts": 0,
                "success_rate": 0.0,
                "step_errors": {},
                "last_attempt":  None
            }
        
        progress = skill_progress[skill_id]
        progress["attempts"] += 1
        
        if attempt["success"]: 
            progress["successful_attempts"] += 1
        
        progress["success_rate"] = progress["successful_attempts"] / progress["attempts"]
        progress["last_attempt"] = attempt["end_time"]
        
        # Step errors ekle
        for error in attempt["step_errors"]:
            step_key = str(error["step_number"])
            if step_key not in progress["step_errors"]:
                progress["step_errors"][step_key] = []
            progress["step_errors"][step_key].append({
                "error_type": error["error_type"],
                "expected_action": error["expected_action"],
                "actual_action": error["actual_action"],
                "timestamp":  error["timestamp"]
            })
    
    return skill_progress


def generate_test_data(num_attempts=100):
    """Tam test verisi üret"""
    base_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone. utc)
    
    users_data = {}
    all_attempts = []
    
    # Kullanıcıları oluştur
    for user_id, user_info in USERS.items():
        phase = "Foundation"
        if user_info["skill_level"] >= 0.8:
            phase = "Advanced"
        elif user_info["skill_level"] >= 0.5:
            phase = "Mobility"
        
        users_data[user_id] = {
            "user_id": user_id,
            "current_phase": phase,
            "skill_progress": {},
            "sessions": [],
            "created_at": get_timestamp(base_time, 0),
            "updated_at": None
        }
    
    # Attempt'leri üret
    attempt_offset = 0
    skill_ids = list(SKILLS.keys())
    user_ids = list(USERS.keys())
    
    for i in range(num_attempts):
        # Rastgele kullanıcı ve skill seç
        user_id = random.choice(user_ids)
        
        # Kullanıcı seviyesine göre skill seç
        user_level = USERS[user_id]["skill_level"]
        
        if user_level < 0.5:
            # Beginner:  kolay skill'ler
            available_skills = [s for s, info in SKILLS.items() if info["difficulty"] in ["easy", "medium"]]
        elif user_level < 0.8:
            # Intermediate: tüm skill'ler
            available_skills = skill_ids
        else:
            # Advanced: zor skill'lere ağırlık
            weights = [3 if SKILLS[s]["difficulty"] in ["hard", "expert"] else 1 for s in skill_ids]
            skill_id = random.choices(skill_ids, weights=weights)[0]
            available_skills = [skill_id]
        
        if len(available_skills) > 1:
            skill_id = random.choice(available_skills)
        else:
            skill_id = available_skills[0]
        
        attempt = generate_attempt(user_id, skill_id, base_time, attempt_offset)
        all_attempts.append(attempt)
        
        attempt_offset += random.randint(5, 15)  # 5-15 dakika arasında
    
    # Her kullanıcı için skill progress hesapla
    for user_id in users_data:
        user_attempts = [a for a in all_attempts if a["user_id"] == user_id]
        users_data[user_id]["skill_progress"] = calculate_skill_progress(user_attempts)
        
        if user_attempts:
            users_data[user_id]["updated_at"] = max(a["end_time"] for a in user_attempts)
    
    return {
        "users": users_data,
        "attempts": all_attempts
    }


def main():
    """Ana fonksiyon"""
    print("=" * 60)
    print("  WHEELCHAIR SKILLS TEST DATA GENERATOR")
    print("=" * 60)
    print()
    
    # 100 attempt üret
    data = generate_test_data(num_attempts=100)
    
    # İstatistikleri göster
    print(f"Generated Data Statistics:")
    print(f"   Users: {len(data['users'])}")
    print(f"   Attempts:  {len(data['attempts'])}")
    print()
    
    # Skill bazlı istatistikler
    skill_stats = {}
    for attempt in data["attempts"]:
        skill_id = attempt["skill_id"]
        if skill_id not in skill_stats:
            skill_stats[skill_id] = {"total":  0, "success":  0, "errors": 0}
        skill_stats[skill_id]["total"] += 1
        if attempt["success"]: 
            skill_stats[skill_id]["success"] += 1
        skill_stats[skill_id]["errors"] += len(attempt["step_errors"])
    
    print("Skill Statistics:")
    for skill_id, stats in sorted(skill_stats. items(), key=lambda x:  x[1]["total"], reverse=True):
        success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"   {skill_id}: {stats['total']} attempts, {success_rate:.0f}% success, {stats['errors']} errors")
    print()
    
    # Kullanıcı bazlı istatistikler
    print("User Statistics:")
    for user_id, user_data in data["users"].items():
        user_attempts = [a for a in data["attempts"] if a["user_id"] == user_id]
        success_count = sum(1 for a in user_attempts if a["success"])
        success_rate = (success_count / len(user_attempts) * 100) if user_attempts else 0
        print(f"   {user_id}: {len(user_attempts)} attempts, {success_rate:.0f}% success, Phase: {user_data['current_phase']}")
    print()
    
    # Dosyaya kaydet
    output_path = os.path.join(os. path.dirname(__file__), "..", "data", "user_progress.json")
    
    # Backup mevcut dosyayı
    if os.path.exists(output_path):
        backup_path = output_path. replace(".json", "_backup.json")
        os.rename(output_path, backup_path)
        print(f"Backed up existing file to: {backup_path}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Data saved to: {output_path}")
    print()
    print("=" * 60)


if __name__ == "__main__": 
    main()