"""
User Progress Manager
=====================
Tekerlekli sandalye beceri eğitimi için kullanıcı ilerleme yönetimi.
Bu modül kullanıcı verilerini JSON dosya tabanlı veritabanında yönetir.
"""

import json
import os
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional

# Dosya yolları
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "user_progress.json")
ERROR_TYPES_PATH = os.path.join(DATA_DIR, "error_types.json")
SKILL_STEPS_DIR = os.path.join(DATA_DIR, "skill_steps")

# Analytics constants
MAX_PROBLEMATIC_ITEMS = 20  # Maximum items to return in problematic steps/actions lists
COMPARISON_THRESHOLD = 0.05  # Threshold for "average" classification in comparisons

# Thread-safe dosya yazma için kilit
_file_lock = threading.Lock()


def _get_timestamp() -> str:
    """ISO 8601 formatında şu anki zamanı döndür"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _generate_id(prefix: str = "") -> str:
    """Benzersiz ID oluştur"""
    unique = uuid.uuid4().hex[:8]
    return f"{prefix}_{unique}" if prefix else unique


class UserProgressManager:
    """
    Kullanıcı ilerleme yönetimi sınıfı.
    Thread-safe dosya işlemleri ile JSON tabanlı veritabanı yönetimi sağlar.
    """
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        UserProgressManager'ı başlat.
        
        Args:
            db_path: Kullanıcı veritabanı dosya yolu
        """
        self.db_path = db_path
        self._ensure_db_exists()
        self._active_attempts: dict[str, dict] = {}  # Aktif denemeler için geçici depo
    
    def _ensure_db_exists(self) -> None:
        """Veritabanı dosyasının var olduğundan emin ol"""
        # Dizinin var olduğundan emin ol
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Dosya yoksa veya boşsa başlat
        if not os.path.exists(self.db_path):
            self._save_db({"users": {}, "attempts": []})
        else:
            # Dosya varsa ama boşsa başlat
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        self._save_db({"users": {}, "attempts": []})
                    else:
                        # JSON geçerli mi kontrol et
                        json.loads(content)
            except (json.JSONDecodeError, FileNotFoundError):
                self._save_db({"users": {}, "attempts": []})
    
    def _load_db(self) -> dict:
        """Veritabanını yükle"""
        with _file_lock:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    def _save_db(self, data: dict) -> None:
        """Veritabanını kaydet (thread-safe)"""
        with _file_lock:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ==================== Kullanıcı İşlemleri ====================
    
    def get_user(self, user_id: str) -> Optional[dict]:
        """
        Kullanıcı bilgilerini getir.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Kullanıcı verisi veya None (bulunamazsa)
        """
        db = self._load_db()
        return db.get("users", {}).get(user_id)
    
    def create_user(self, user_id: str) -> dict:
        """
        Yeni kullanıcı oluştur.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Oluşturulan kullanıcı verisi
        """
        db = self._load_db()
        
        # Kullanıcı zaten varsa mevcut kaydı döndür
        if user_id in db.get("users", {}):
            return db["users"][user_id]
        
        # Yeni kullanıcı oluştur
        user = {
            "user_id": user_id,
            "current_phase": "Foundation",  # Başlangıç fazı
            "skill_progress": {},
            "sessions": [],
            "created_at": _get_timestamp(),
            "updated_at": None
        }
        
        if "users" not in db:
            db["users"] = {}
        db["users"][user_id] = user
        
        self._save_db(db)
        return user
    
    # ==================== Skill Attempt İşlemleri ====================
    
    def start_skill_attempt(self, user_id: str, skill_id: str) -> str:
        """
        Yeni bir beceri denemesi başlat.
        
        Args:
            user_id: Kullanıcı kimliği
            skill_id: Beceri kimliği
            
        Returns:
            Deneme kimliği (attempt_id)
        """
        # Kullanıcı yoksa oluştur
        if not self.get_user(user_id):
            self.create_user(user_id)
        
        attempt_id = _generate_id("att")
        
        attempt = {
            "attempt_id": attempt_id,
            "user_id": user_id,
            "skill_id": skill_id,
            "start_time": _get_timestamp(),
            "end_time": None,
            "step_inputs": [],
            "step_errors": [],
            "success": None
        }
        
        # Aktif denemeye ekle
        self._active_attempts[attempt_id] = attempt
        
        return attempt_id
    
    def record_step_input(
        self,
        attempt_id: str,
        step_number: int,
        expected_input: str,
        actual_input: str,
        timestamp: Optional[str] = None
    ) -> bool:
        """
        Adım input'unu kaydet.
        
        Args:
            attempt_id: Deneme kimliği
            step_number: Adım numarası
            expected_input: Beklenen input
            actual_input: Gerçekleşen input
            timestamp: Zaman damgası (opsiyonel)
            
        Returns:
            Başarılı mı?
        """
        if attempt_id not in self._active_attempts:
            return False
        
        input_record = {
            "step_number": step_number,
            "expected_input": expected_input,
            "actual_input": actual_input,
            "is_correct": expected_input == actual_input,
            "timestamp": timestamp or _get_timestamp()
        }
        
        self._active_attempts[attempt_id]["step_inputs"].append(input_record)
        return True
    
    def record_step_error(
        self,
        attempt_id: str,
        step_number: int,
        error_type: str,
        expected_action: str,
        actual_action: str
    ) -> bool:
        """
        Adım hatasını kaydet.
        
        Args:
            attempt_id: Deneme kimliği
            step_number: Adım numarası
            error_type: Hata tipi
            expected_action: Beklenen aksiyon
            actual_action: Gerçekleşen aksiyon
            
        Returns:
            Başarılı mı?
        """
        if attempt_id not in self._active_attempts:
            return False
        
        error_record = {
            "step_number": step_number,
            "error_type": error_type,
            "expected_action": expected_action,
            "actual_action": actual_action,
            "timestamp": _get_timestamp()
        }
        
        self._active_attempts[attempt_id]["step_errors"].append(error_record)
        return True
    
    def complete_skill_attempt(self, attempt_id: str, success: bool) -> bool:
        """
        Beceri denemesini tamamla.
        
        Args:
            attempt_id: Deneme kimliği
            success: Başarılı mı?
            
        Returns:
            İşlem başarılı mı?
        """
        if attempt_id not in self._active_attempts:
            return False
        
        attempt = self._active_attempts[attempt_id]
        attempt["end_time"] = _get_timestamp()
        attempt["success"] = success
        
        # Veritabanını güncelle
        db = self._load_db()
        
        user_id = attempt["user_id"]
        skill_id = attempt["skill_id"]
        
        # Kullanıcının skill_progress'ini güncelle
        if user_id in db.get("users", {}):
            user = db["users"][user_id]
            
            if skill_id not in user["skill_progress"]:
                user["skill_progress"][skill_id] = {
                    "skill_id": skill_id,
                    "attempts": 0,
                    "successful_attempts": 0,
                    "success_rate": 0.0,
                    "step_errors": {},
                    "last_attempt": None
                }
            
            progress = user["skill_progress"][skill_id]
            progress["attempts"] += 1
            if success:
                progress["successful_attempts"] += 1
            progress["success_rate"] = progress["successful_attempts"] / progress["attempts"]
            progress["last_attempt"] = attempt["end_time"]
            
            # Hataları step_errors'a ekle
            for error in attempt["step_errors"]:
                step_key = str(error["step_number"])
                if step_key not in progress["step_errors"]:
                    progress["step_errors"][step_key] = []
                progress["step_errors"][step_key].append({
                    "error_type": error["error_type"],
                    "expected_action": error["expected_action"],
                    "actual_action": error["actual_action"],
                    "timestamp": error["timestamp"]
                })
            
            user["updated_at"] = _get_timestamp()
        
        # Denemeyi attempts listesine ekle
        if "attempts" not in db:
            db["attempts"] = []
        db["attempts"].append(attempt)
        
        self._save_db(db)
        
        # Aktif denemelerden kaldır
        del self._active_attempts[attempt_id]
        
        return True
    
    # ==================== Analytics ====================
    
    def get_skill_stats(self, user_id: str, skill_id: str) -> Optional[dict]:
        """
        Belirli bir beceri için istatistikleri getir.
        
        Args:
            user_id: Kullanıcı kimliği
            skill_id: Beceri kimliği
            
        Returns:
            Beceri istatistikleri
        """
        user = self.get_user(user_id)
        if not user:
            return None
        
        progress = user.get("skill_progress", {}).get(skill_id)
        if not progress:
            return None
        
        # Toplam hata sayısını hesapla
        total_errors = sum(
            len(errors) for errors in progress.get("step_errors", {}).values()
        )
        
        return {
            "skill_id": skill_id,
            "attempts": progress["attempts"],
            "successful_attempts": progress["successful_attempts"],
            "success_rate": progress["success_rate"],
            "total_errors": total_errors,
            "last_attempt": progress["last_attempt"],
            "error_by_step": {
                step: len(errors) 
                for step, errors in progress.get("step_errors", {}).items()
            }
        }
    
    def get_common_errors(self, user_id: str, skill_id: Optional[str] = None) -> list[dict]:
        """
        Kullanıcının en sık yaptığı hataları getir.
        
        Args:
            user_id: Kullanıcı kimliği
            skill_id: Beceri kimliği (opsiyonel, belirtilmezse tüm beceriler)
            
        Returns:
            Hata listesi (sıklığa göre sıralı)
        """
        user = self.get_user(user_id)
        if not user:
            return []
        
        # Hata sayımı için dictionary
        error_counts: dict[str, dict] = {}
        
        skills_to_check = (
            [skill_id] if skill_id 
            else list(user.get("skill_progress", {}).keys())
        )
        
        for sid in skills_to_check:
            progress = user.get("skill_progress", {}).get(sid, {})
            for step_num, errors in progress.get("step_errors", {}).items():
                for error in errors:
                    error_type = error.get("error_type", "unknown")
                    key = f"{sid}:{step_num}:{error_type}"
                    
                    if key not in error_counts:
                        error_counts[key] = {
                            "skill_id": sid,
                            "step_number": int(step_num),
                            "error_type": error_type,
                            "expected_action": error.get("expected_action", ""),
                            "actual_action": error.get("actual_action", ""),
                            "count": 0
                        }
                    error_counts[key]["count"] += 1
        
        # Sıklığa göre sırala
        return sorted(
            error_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )
    
    def get_weak_steps(self, user_id: str, skill_id: str) -> list[dict]:
        """
        En çok hata yapılan adımları getir.
        
        Args:
            user_id: Kullanıcı kimliği
            skill_id: Beceri kimliği
            
        Returns:
            Zayıf adımlar listesi (hata sayısına göre sıralı)
        """
        stats = self.get_skill_stats(user_id, skill_id)
        if not stats:
            return []
        
        error_by_step = stats.get("error_by_step", {})
        
        weak_steps = [
            {
                "step_number": int(step_num),
                "error_count": count
            }
            for step_num, count in error_by_step.items()
        ]
        
        # Hata sayısına göre sırala
        return sorted(weak_steps, key=lambda x: x["error_count"], reverse=True)
    
    # ==================== Progress ====================
    
    def calculate_success_rate(self, user_id: str, skill_id: str) -> float:
        """
        Belirli bir beceri için başarı oranını hesapla.
        
        Args:
            user_id: Kullanıcı kimliği
            skill_id: Beceri kimliği
            
        Returns:
            Başarı oranı (0.0 - 1.0)
        """
        user = self.get_user(user_id)
        if not user:
            return 0.0
        
        progress = user.get("skill_progress", {}).get(skill_id)
        if not progress or progress.get("attempts", 0) == 0:
            return 0.0
        
        return progress.get("success_rate", 0.0)
    
    def get_recommended_skills(self, user_id: str) -> list[dict]:
        """
        Kullanıcı için önerilen becerileri getir.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Önerilen beceriler listesi
        """
        user = self.get_user(user_id)
        if not user:
            return []
        
        current_phase = user.get("current_phase", "Foundation")
        skill_progress = user.get("skill_progress", {})
        
        # Faz-seviye eşlemesi
        phase_to_levels = {
            "Foundation": ["basic", "beginner"],
            "Mobility": ["intermediate"],
            "Advanced": ["advanced", "emergency"]
        }
        
        # Skill steps index dosyasını yükle
        index_path = os.path.join(SKILL_STEPS_DIR, "_index.json")
        if not os.path.exists(index_path):
            return []
        
        with open(index_path, "r", encoding="utf-8") as f:
            skills_index = json.load(f)
        
        # Önerilen becerileri belirle
        recommendations = []
        target_levels = phase_to_levels.get(current_phase, ["basic", "beginner"])
        
        for skill in skills_index:
            skill_id = skill["skill_id"]
            level = skill["level"]
            
            # Sadece mevcut fazın seviyelerindeki becerileri öner
            if level not in target_levels:
                continue
            
            progress = skill_progress.get(skill_id, {})
            success_rate = progress.get("success_rate", 0.0)
            attempts = progress.get("attempts", 0)
            
            # Öncelik: düşük başarı oranı veya hiç denenmemiş
            priority = 0
            reason = ""
            
            if attempts == 0:
                priority = 3
                reason = "Henüz denenmedi"
            elif success_rate < 0.5:
                priority = 2
                reason = f"Düşük başarı oranı: {success_rate:.0%}"
            elif success_rate < 0.8:
                priority = 1
                reason = f"Geliştirilebilir: {success_rate:.0%}"
            else:
                continue  # Yüksek başarı oranı, öneri listesine ekleme
            
            recommendations.append({
                "skill_id": skill_id,
                "title": skill["title"],
                "level": level,
                "attempts": attempts,
                "success_rate": success_rate,
                "priority": priority,
                "reason": reason
            })
        
        # Önceliğe göre sırala
        return sorted(recommendations, key=lambda x: x["priority"], reverse=True)
    
    def update_phase(self, user_id: str) -> str:
        """
        Kullanıcının fazını kontrol et ve gerekirse güncelle.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Yeni faz adı
        """
        user = self.get_user(user_id)
        if not user:
            return "Foundation"
        
        skill_progress = user.get("skill_progress", {})
        current_phase = user.get("current_phase", "Foundation")
        
        # Faz geçiş kriterleri
        # Foundation -> Mobility: beginner becerilerde %70+ başarı
        # Mobility -> Advanced: intermediate becerilerde %70+ başarı
        
        beginner_skills = [
            "beginner-wheeling-forward", "beginner-wheeling-backward",
            "beginner-turn-on-spot", "beginner-turn-forward", "beginner-turn-backward"
        ]
        
        intermediate_skills = [
            "intermediate-ramps-up", "intermediate-ramps-down",
            "intermediate-popping-casters", "intermediate-obstacles-thresholds"
        ]
        
        def check_phase_completion(skills: list[str], threshold: float = 0.7) -> bool:
            completed = 0
            for skill_id in skills:
                progress = skill_progress.get(skill_id, {})
                if progress.get("success_rate", 0) >= threshold:
                    completed += 1
            return completed >= len(skills) * 0.6  # %60'ı tamamlanmış olmalı
        
        new_phase = current_phase
        
        if current_phase == "Foundation":
            if check_phase_completion(beginner_skills):
                new_phase = "Mobility"
        elif current_phase == "Mobility":
            if check_phase_completion(intermediate_skills):
                new_phase = "Advanced"
        
        # Faz değiştiyse güncelle
        if new_phase != current_phase:
            db = self._load_db()
            if user_id in db.get("users", {}):
                db["users"][user_id]["current_phase"] = new_phase
                db["users"][user_id]["updated_at"] = _get_timestamp()
                self._save_db(db)
        
        return new_phase
    
    # ==================== Global Analytics ====================
    
    def get_global_error_stats(self) -> dict:
        """
        Tüm kullanıcıların hata istatistiklerini getir.
        
        Returns:
            Global hata istatistikleri
        """
        db = self._load_db()
        attempts = db.get("attempts", [])
        
        # Toplam sayılar
        total_attempts = len(attempts)
        total_users = len(set(att["user_id"] for att in attempts))
        
        # Skill bazlı istatistikler
        skill_stats = {}
        for attempt in attempts:
            skill_id = attempt["skill_id"]
            if skill_id not in skill_stats:
                skill_stats[skill_id] = {
                    "total_attempts": 0,
                    "failed_attempts": 0,
                    "errors": [],
                    "step_errors": {}
                }
            
            skill_stats[skill_id]["total_attempts"] += 1
            if not attempt.get("success", False):
                skill_stats[skill_id]["failed_attempts"] += 1
            
            # Hataları topla
            for error in attempt.get("step_errors", []):
                skill_stats[skill_id]["errors"].append(error)
                step_num = str(error["step_number"])
                if step_num not in skill_stats[skill_id]["step_errors"]:
                    skill_stats[skill_id]["step_errors"][step_num] = []
                skill_stats[skill_id]["step_errors"][step_num].append(error)
        
        # Skill summary oluştur
        skill_summary = []
        for skill_id, stats in skill_stats.items():
            total_errors = len(stats["errors"])
            failure_rate = stats["failed_attempts"] / stats["total_attempts"] if stats["total_attempts"] > 0 else 0
            
            # En problemli adımı bul
            most_problematic_step = None
            max_errors = 0
            for step_num, errors in stats["step_errors"].items():
                if len(errors) > max_errors:
                    max_errors = len(errors)
                    most_problematic_step = step_num
            
            skill_summary.append({
                "skill_id": skill_id,
                "total_attempts": stats["total_attempts"],
                "failed_attempts": stats["failed_attempts"],
                "failure_rate": round(failure_rate, 2),
                "total_errors": total_errors,
                "most_problematic_step": most_problematic_step
            })
        
        # Problematic steps - tüm skilllerden en çok hata yapılan adımlar
        problematic_steps = []
        for skill_id, stats in skill_stats.items():
            for step_num, errors in stats["step_errors"].items():
                # En yaygın hata tipini bul
                error_types = {}
                for error in errors:
                    error_type = error.get("error_type", "unknown")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                
                most_common_error = max(error_types, key=error_types.get) if error_types else None
                
                problematic_steps.append({
                    "skill_id": skill_id,
                    "step_number": int(step_num),
                    "error_count": len(errors),
                    "most_common_error": most_common_error
                })
        
        # Hata sayısına göre sırala
        problematic_steps.sort(key=lambda x: x["error_count"], reverse=True)
        
        # Action confusion matrix - hangi action yerine ne yapılıyor
        action_confusion = {}
        for attempt in attempts:
            for error in attempt.get("step_errors", []):
                expected = error.get("expected_action", "")
                actual = error.get("actual_action", "")
                
                if expected and actual and expected != actual:
                    key = f"{expected}:{actual}"
                    if key not in action_confusion:
                        action_confusion[key] = {
                            "expected": expected,
                            "actual": actual,
                            "count": 0,
                            "description": f"Users press {actual} instead of {expected}"
                        }
                    action_confusion[key]["count"] += 1
        
        # Sayıya göre sırala
        action_confusion_list = sorted(
            action_confusion.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        return {
            "total_attempts": total_attempts,
            "total_users": total_users,
            "skill_summary": sorted(skill_summary, key=lambda x: x["failure_rate"], reverse=True),
            "problematic_steps": problematic_steps[:MAX_PROBLEMATIC_ITEMS],
            "action_confusion": action_confusion_list[:MAX_PROBLEMATIC_ITEMS],
            "generated_at": _get_timestamp()
        }
    
    def get_skill_error_stats(self, skill_id: str) -> Optional[dict]:
        """
        Belirli bir skill için detaylı hata analizi.
        
        Args:
            skill_id: Beceri kimliği
            
        Returns:
            Skill hata istatistikleri
        """
        db = self._load_db()
        attempts = db.get("attempts", [])
        
        # Bu skill için denemeleri filtrele
        skill_attempts = [att for att in attempts if att["skill_id"] == skill_id]
        
        if not skill_attempts:
            return None
        
        # Step bazlı istatistikler
        step_stats = {}
        for attempt in skill_attempts:
            for error in attempt.get("step_errors", []):
                step_num = error["step_number"]
                if step_num not in step_stats:
                    step_stats[step_num] = {
                        "step_number": step_num,
                        "total_errors": 0,
                        "error_types": {},
                        "wrong_actions": []
                    }
                
                step_stats[step_num]["total_errors"] += 1
                
                error_type = error.get("error_type", "unknown")
                step_stats[step_num]["error_types"][error_type] = \
                    step_stats[step_num]["error_types"].get(error_type, 0) + 1
                
                step_stats[step_num]["wrong_actions"].append({
                    "expected": error.get("expected_action", ""),
                    "actual": error.get("actual_action", "")
                })
        
        # Step istatistiklerini işle
        step_error_rates = []
        for step_num, stats in step_stats.items():
            # En yaygın hata tipini bul
            common_errors = sorted(
                stats["error_types"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # En yaygın yanlış actionları bul
            wrong_action_counts = {}
            for wa in stats["wrong_actions"]:
                key = f"{wa['expected']}:{wa['actual']}"
                wrong_action_counts[key] = wrong_action_counts.get(key, 0) + 1
            
            common_wrong_actions = sorted(
                wrong_action_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            step_error_rates.append({
                "step_number": step_num,
                "error_rate": stats["total_errors"] / len(skill_attempts),
                "total_errors": stats["total_errors"],
                "common_error_types": [{"type": et[0], "count": et[1]} for et in common_errors[:3]],
                "common_wrong_actions": [
                    {
                        "expected": cwa[0].split(":")[0],
                        "actual": cwa[0].split(":")[1],
                        "count": cwa[1]
                    }
                    for cwa in common_wrong_actions
                ]
            })
        
        # En zor adımı bul
        most_difficult_step = max(step_error_rates, key=lambda x: x["error_rate"]) if step_error_rates else None
        
        return {
            "skill_id": skill_id,
            "total_attempts": len(skill_attempts),
            "step_error_rates": sorted(step_error_rates, key=lambda x: x["error_rate"], reverse=True),
            "most_difficult_step": most_difficult_step,
            "generated_at": _get_timestamp()
        }
    
    def clear_user_progress(self, user_id: str) -> bool:
        """
        Kullanıcının tüm ilerleme verilerini sil.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Başarılı mı?
        """
        db = self._load_db()
        
        # Kullanıcı yoksa False döndür
        if user_id not in db.get("users", {}):
            return False
        
        # Kullanıcının skill_progress'ini sıfırla
        db["users"][user_id]["skill_progress"] = {}
        db["users"][user_id]["sessions"] = []
        db["users"][user_id]["updated_at"] = _get_timestamp()
        
        # Bu kullanıcıya ait attempts'leri sil
        if "attempts" in db:
            db["attempts"] = [
                att for att in db["attempts"]
                if att["user_id"] != user_id
            ]
        
        self._save_db(db)
        return True
    
    def get_skill_comparisons(self, user_id: str) -> list[dict]:
        """
        Kullanıcının performansını global ortalamayla karşılaştır.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Karşılaştırma listesi
        """
        user = self.get_user(user_id)
        if not user:
            return []
        
        db = self._load_db()
        attempts = db.get("attempts", [])
        
        # Global success rate'leri hesapla
        global_rates = {}
        for attempt in attempts:
            skill_id = attempt["skill_id"]
            if skill_id not in global_rates:
                global_rates[skill_id] = {"total": 0, "success": 0}
            
            global_rates[skill_id]["total"] += 1
            if attempt.get("success", False):
                global_rates[skill_id]["success"] += 1
        
        # Kullanıcının denediği her skill için karşılaştırma yap
        comparisons = []
        skill_progress = user.get("skill_progress", {})
        
        for skill_id, progress in skill_progress.items():
            your_success_rate = progress.get("success_rate", 0.0)
            
            # Global success rate hesapla
            if skill_id in global_rates and global_rates[skill_id]["total"] > 0:
                global_success_rate = global_rates[skill_id]["success"] / global_rates[skill_id]["total"]
            else:
                global_success_rate = 0.0
            
            # Karşılaştırma yap
            comparison = "above_average" if your_success_rate > global_success_rate else "below_average"
            if abs(your_success_rate - global_success_rate) < COMPARISON_THRESHOLD:
                comparison = "average"
            
            comparisons.append({
                "skill_id": skill_id,
                "your_success_rate": round(your_success_rate, 2),
                "global_success_rate": round(global_success_rate, 2),
                "comparison": comparison
            })
        
        return comparisons
    
    # ==================== Training Plan ====================
    
    def generate_training_plan(self, user_id: str) -> dict:
        """
        Kullanıcı için kişiselleştirilmiş eğitim planı oluştur.
        
        Args:
            user_id: Kullanıcı kimliği
            
        Returns:
            Eğitim planı
        """
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id)
        
        current_phase = user.get("current_phase", "Foundation")
        recommended = self.get_recommended_skills(user_id)
        common_errors = self.get_common_errors(user_id)
        
        # En sık hata yapılan 3 beceriyi belirle
        error_skills = {}
        for error in common_errors[:10]:
            skill_id = error.get("skill_id")
            if skill_id not in error_skills:
                error_skills[skill_id] = {
                    "skill_id": skill_id,
                    "total_errors": 0,
                    "error_types": []
                }
            error_skills[skill_id]["total_errors"] += error.get("count", 0)
            error_skills[skill_id]["error_types"].append(error.get("error_type"))
        
        focus_skills = sorted(
            error_skills.values(),
            key=lambda x: x["total_errors"],
            reverse=True
        )[:3]
        
        # Global insights
        global_stats = self.get_global_error_stats()
        most_failed_skills = [
            skill["skill_id"] 
            for skill in global_stats.get("skill_summary", [])[:3]
        ]
        
        common_mistakes = global_stats.get("action_confusion", [])[:5]
        problematic_steps = global_stats.get("problematic_steps", [])[:5]
        
        # User's common errors
        your_common_errors = self.get_common_errors(user_id)[:10]
        
        # Skill comparisons
        skill_comparisons = self.get_skill_comparisons(user_id)
        
        plan = {
            "user_id": user_id,
            "current_phase": current_phase,
            "generated_at": _get_timestamp(),
            "recommended_skills": recommended[:5],
            "focus_skills": focus_skills,
            "session_goals": [],
            "notes": [],
            "global_insights": {
                "most_failed_skills": most_failed_skills,
                "common_mistakes": common_mistakes,
                "problematic_steps": problematic_steps
            },
            "your_common_errors": your_common_errors,
            "skill_comparisons": skill_comparisons
        }
        
        # Oturum hedeflerini belirle
        if recommended:
            plan["session_goals"].append(
                f"Öncelikli beceri: {recommended[0]['title']} - {recommended[0]['reason']}"
            )
        
        if focus_skills:
            plan["notes"].append(
                f"Dikkat: '{focus_skills[0]['skill_id']}' becerisinde sık hata yapılıyor"
            )
        
        # Faz bazlı notlar
        if current_phase == "Foundation":
            plan["notes"].append("Temel hareketlere odaklanın: ileri, geri, dönüş")
        elif current_phase == "Mobility":
            plan["notes"].append("Arazi becerileri ve engellerle çalışın")
        else:
            plan["notes"].append("İleri seviye teknikler ve acil durum becerileri")
        
        return plan
    def record_step_telemetry(self, attempt_id: str, payload: dict) -> bool:
        """
        Store a richer telemetry payload for an active attempt.
        Payload is expected to be a dict with keys like:
        stepNumber, expectedAction, actualAction, success, holdDuration, peakForce, distance, assistUsed, timestamp
        """
        if attempt_id not in self._active_attempts:
            return False
        attempt = self._active_attempts[attempt_id]
        # normalize key names
        step_number = payload.get("stepNumber") or payload.get("step_number") or 0
        telemetry = {
            "step_number": step_number,
            "expected_action": payload.get("expectedAction") or payload.get("expected_action"),
            "actual_action": payload.get("actualAction") or payload.get("actual_action"),
            "success": payload.get("success", False),
            "metrics": {
                "hold_duration": payload.get("holdDuration") or payload.get("hold_duration") or 0,
                "peak_force": payload.get("peakForce") or payload.get("peak_force") or 0,
                "distance": payload.get("distance", 0),
                "assist_used": payload.get("assistUsed") or payload.get("assist_used", False)
            },
            "timestamp": payload.get("timestamp") or _get_timestamp()
        }
        if "step_telemetry" not in attempt:
            attempt["step_telemetry"] = []
        attempt["step_telemetry"].append(telemetry)
        return True


# Test için
if __name__ == "__main__":
    import tempfile
    
    # Geçici dosya ile test
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        test_db_path = f.name
    
    try:
        manager = UserProgressManager(test_db_path)
        
        # Kullanıcı oluştur
        user = manager.create_user("test_user_001")
        print(f"Kullanıcı oluşturuldu: {user['user_id']}")
        
        # Deneme başlat
        attempt_id = manager.start_skill_attempt("test_user_001", "intermediate-curb-up-help")
        print(f"Deneme başlatıldı: {attempt_id}")
        
        # Input kaydet
        manager.record_step_input(attempt_id, 1, "W", "W")
        manager.record_step_input(attempt_id, 2, "SPACE", "SPACE")
        manager.record_step_input(attempt_id, 3, "X", "W")  # Yanlış input
        
        # Hata kaydet
        manager.record_step_error(
            attempt_id, 3, "wrong_input",
            "pop_casters", "move_forward"
        )
        
        # Denemeyi tamamla
        manager.complete_skill_attempt(attempt_id, success=False)
        print("Deneme tamamlandı")
        
        # İstatistikleri getir
        stats = manager.get_skill_stats("test_user_001", "intermediate-curb-up-help")
        print(f"İstatistikler: {stats}")
        
        # Hataları getir
        errors = manager.get_common_errors("test_user_001")
        print(f"Yaygın hatalar: {errors}")
        
    finally:
        # Temizlik
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
