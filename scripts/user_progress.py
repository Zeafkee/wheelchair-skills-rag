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
        
        plan = {
            "user_id": user_id,
            "current_phase": current_phase,
            "generated_at": _get_timestamp(),
            "recommended_skills": recommended[:5],
            "focus_skills": focus_skills,
            "session_goals": [],
            "notes": []
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
