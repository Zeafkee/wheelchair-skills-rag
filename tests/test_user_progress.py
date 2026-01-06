"""
User Progress Manager Unit Tests
================================
UserProgressManager sınıfı için birim testleri.
"""

import os
import sys
import json
import tempfile
import pytest

# Scripts dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from user_progress import UserProgressManager, _get_timestamp, _generate_id


class TestHelperFunctions:
    """Yardımcı fonksiyonların testleri"""
    
    def test_get_timestamp_format(self):
        """Timestamp ISO 8601 formatında olmalı"""
        ts = _get_timestamp()
        assert ts.endswith("Z")
        # ISO 8601 formatını kontrol et
        assert "T" in ts
        # Tarih ve saat bölümleri olmalı
        parts = ts.replace("Z", "").split("T")
        assert len(parts) == 2
    
    def test_generate_id_with_prefix(self):
        """Prefix ile ID oluşturma"""
        id1 = _generate_id("test")
        assert id1.startswith("test_")
        assert len(id1) > 5
    
    def test_generate_id_without_prefix(self):
        """Prefix olmadan ID oluşturma"""
        id1 = _generate_id()
        assert "_" not in id1
        assert len(id1) == 8
    
    def test_generate_id_uniqueness(self):
        """ID'ler benzersiz olmalı"""
        ids = [_generate_id("test") for _ in range(100)]
        assert len(set(ids)) == 100


class TestUserProgressManager:
    """UserProgressManager sınıfının testleri"""
    
    @pytest.fixture
    def temp_db(self):
        """Geçici veritabanı dosyası"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Temizlik
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def manager(self, temp_db):
        """Test için UserProgressManager örneği"""
        return UserProgressManager(temp_db)
    
    # ==================== User Tests ====================
    
    def test_create_user(self, manager):
        """Yeni kullanıcı oluşturma"""
        user = manager.create_user("user_001")
        
        assert user["user_id"] == "user_001"
        assert user["current_phase"] == "Foundation"
        assert user["skill_progress"] == {}
        assert user["sessions"] == []
        assert "created_at" in user
    
    def test_create_user_duplicate(self, manager):
        """Aynı kullanıcıyı tekrar oluşturma"""
        user1 = manager.create_user("user_001")
        user2 = manager.create_user("user_001")
        
        # Aynı kullanıcı döndürülmeli
        assert user1["user_id"] == user2["user_id"]
        assert user1["created_at"] == user2["created_at"]
    
    def test_get_user(self, manager):
        """Kullanıcı bilgilerini getirme"""
        manager.create_user("user_001")
        user = manager.get_user("user_001")
        
        assert user is not None
        assert user["user_id"] == "user_001"
    
    def test_get_user_not_found(self, manager):
        """Var olmayan kullanıcı"""
        user = manager.get_user("nonexistent")
        assert user is None
    
    # ==================== Skill Attempt Tests ====================
    
    def test_start_skill_attempt(self, manager):
        """Beceri denemesi başlatma"""
        manager.create_user("user_001")
        attempt_id = manager.start_skill_attempt("user_001", "skill_001")
        
        assert attempt_id.startswith("att_")
        assert len(attempt_id) > 4
    
    def test_start_skill_attempt_auto_create_user(self, manager):
        """Kullanıcı yoksa otomatik oluşturma"""
        attempt_id = manager.start_skill_attempt("new_user", "skill_001")
        
        assert attempt_id is not None
        # Kullanıcı oluşturulmuş olmalı
        user = manager.get_user("new_user")
        assert user is not None
    
    def test_record_step_input(self, manager):
        """Adım input'u kaydetme"""
        attempt_id = manager.start_skill_attempt("user_001", "skill_001")
        
        success = manager.record_step_input(attempt_id, 1, "W", "W")
        assert success is True
    
    def test_record_step_input_invalid_attempt(self, manager):
        """Geçersiz deneme için input kaydetme"""
        success = manager.record_step_input("invalid_id", 1, "W", "W")
        assert success is False
    
    def test_record_step_error(self, manager):
        """Adım hatası kaydetme"""
        attempt_id = manager.start_skill_attempt("user_001", "skill_001")
        
        success = manager.record_step_error(
            attempt_id, 3, "wrong_input",
            "pop_casters", "move_forward"
        )
        assert success is True
    
    def test_record_step_error_invalid_attempt(self, manager):
        """Geçersiz deneme için hata kaydetme"""
        success = manager.record_step_error(
            "invalid_id", 3, "wrong_input",
            "pop_casters", "move_forward"
        )
        assert success is False
    
    def test_complete_skill_attempt_success(self, manager):
        """Başarılı deneme tamamlama"""
        attempt_id = manager.start_skill_attempt("user_001", "skill_001")
        manager.record_step_input(attempt_id, 1, "W", "W")
        
        success = manager.complete_skill_attempt(attempt_id, success=True)
        assert success is True
        
        # İstatistikler güncellenmeli
        stats = manager.get_skill_stats("user_001", "skill_001")
        assert stats["attempts"] == 1
        assert stats["successful_attempts"] == 1
        assert stats["success_rate"] == 1.0
    
    def test_complete_skill_attempt_failure(self, manager):
        """Başarısız deneme tamamlama"""
        attempt_id = manager.start_skill_attempt("user_001", "skill_001")
        manager.record_step_input(attempt_id, 1, "W", "S")  # Yanlış input
        manager.record_step_error(attempt_id, 1, "wrong_input", "move_forward", "move_backward")
        
        success = manager.complete_skill_attempt(attempt_id, success=False)
        assert success is True
        
        # İstatistikler güncellenmeli
        stats = manager.get_skill_stats("user_001", "skill_001")
        assert stats["attempts"] == 1
        assert stats["successful_attempts"] == 0
        assert stats["success_rate"] == 0.0
    
    def test_complete_skill_attempt_invalid(self, manager):
        """Geçersiz deneme tamamlama"""
        success = manager.complete_skill_attempt("invalid_id", success=True)
        assert success is False
    
    # ==================== Analytics Tests ====================
    
    def test_get_skill_stats(self, manager):
        """Beceri istatistiklerini getirme"""
        # İlk deneme - başarılı
        attempt1 = manager.start_skill_attempt("user_001", "skill_001")
        manager.complete_skill_attempt(attempt1, success=True)
        
        # İkinci deneme - başarısız
        attempt2 = manager.start_skill_attempt("user_001", "skill_001")
        manager.record_step_error(attempt2, 1, "wrong_input", "move_forward", "move_backward")
        manager.complete_skill_attempt(attempt2, success=False)
        
        stats = manager.get_skill_stats("user_001", "skill_001")
        
        assert stats["skill_id"] == "skill_001"
        assert stats["attempts"] == 2
        assert stats["successful_attempts"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["total_errors"] == 1
    
    def test_get_skill_stats_not_found(self, manager):
        """Var olmayan beceri istatistikleri"""
        manager.create_user("user_001")
        stats = manager.get_skill_stats("user_001", "nonexistent")
        assert stats is None
    
    def test_get_common_errors(self, manager):
        """Yaygın hataları getirme"""
        # Birden fazla hata oluştur
        for _ in range(3):
            attempt = manager.start_skill_attempt("user_001", "skill_001")
            manager.record_step_error(attempt, 1, "wrong_input", "move_forward", "move_backward")
            manager.complete_skill_attempt(attempt, success=False)
        
        for _ in range(2):
            attempt = manager.start_skill_attempt("user_001", "skill_001")
            manager.record_step_error(attempt, 2, "timing_error", "brake", "move_forward")
            manager.complete_skill_attempt(attempt, success=False)
        
        errors = manager.get_common_errors("user_001")
        
        assert len(errors) == 2
        # En sık hata ilk sırada olmalı
        assert errors[0]["count"] == 3
        assert errors[0]["error_type"] == "wrong_input"
    
    def test_get_common_errors_by_skill(self, manager):
        """Belirli beceri için yaygın hataları getirme"""
        # Farklı beceriler için hatalar
        attempt1 = manager.start_skill_attempt("user_001", "skill_001")
        manager.record_step_error(attempt1, 1, "wrong_input", "a", "b")
        manager.complete_skill_attempt(attempt1, success=False)
        
        attempt2 = manager.start_skill_attempt("user_001", "skill_002")
        manager.record_step_error(attempt2, 1, "timing_error", "c", "d")
        manager.complete_skill_attempt(attempt2, success=False)
        
        # Sadece skill_001 hataları
        errors = manager.get_common_errors("user_001", "skill_001")
        
        assert len(errors) == 1
        assert errors[0]["skill_id"] == "skill_001"
    
    def test_get_weak_steps(self, manager):
        """Zayıf adımları getirme"""
        # Farklı adımlarda hatalar oluştur
        for _ in range(3):
            attempt = manager.start_skill_attempt("user_001", "skill_001")
            manager.record_step_error(attempt, 2, "wrong_input", "a", "b")
            manager.complete_skill_attempt(attempt, success=False)
        
        for _ in range(1):
            attempt = manager.start_skill_attempt("user_001", "skill_001")
            manager.record_step_error(attempt, 1, "wrong_input", "c", "d")
            manager.complete_skill_attempt(attempt, success=False)
        
        weak_steps = manager.get_weak_steps("user_001", "skill_001")
        
        assert len(weak_steps) == 2
        # En çok hata yapılan adım ilk sırada
        assert weak_steps[0]["step_number"] == 2
        assert weak_steps[0]["error_count"] == 3
    
    # ==================== Progress Tests ====================
    
    def test_calculate_success_rate(self, manager):
        """Başarı oranı hesaplama"""
        # 2 başarılı, 2 başarısız deneme
        for success in [True, True, False, False]:
            attempt = manager.start_skill_attempt("user_001", "skill_001")
            manager.complete_skill_attempt(attempt, success=success)
        
        rate = manager.calculate_success_rate("user_001", "skill_001")
        assert rate == 0.5
    
    def test_calculate_success_rate_no_attempts(self, manager):
        """Deneme yoksa başarı oranı 0"""
        manager.create_user("user_001")
        rate = manager.calculate_success_rate("user_001", "skill_001")
        assert rate == 0.0
    
    def test_get_recommended_skills(self, manager):
        """Önerilen becerileri getirme"""
        manager.create_user("user_001")
        
        # Öneri için skill_steps index dosyası gerekli
        # Bu test gerçek dosya olmadan çalışmayabilir
        recommendations = manager.get_recommended_skills("user_001")
        
        # Boş liste veya öneri listesi olabilir
        assert isinstance(recommendations, list)
    
    def test_update_phase_no_change(self, manager):
        """Faz güncelleme - değişiklik yok"""
        manager.create_user("user_001")
        new_phase = manager.update_phase("user_001")
        
        # Yeterli ilerleme olmadan faz değişmemeli
        assert new_phase == "Foundation"
    
    # ==================== Training Plan Tests ====================
    
    def test_generate_training_plan(self, manager):
        """Eğitim planı oluşturma"""
        manager.create_user("user_001")
        plan = manager.generate_training_plan("user_001")
        
        assert plan["user_id"] == "user_001"
        assert "current_phase" in plan
        assert "generated_at" in plan
        assert "recommended_skills" in plan
        assert "focus_skills" in plan
        assert "session_goals" in plan
        assert "notes" in plan
    
    def test_generate_training_plan_new_user(self, manager):
        """Yeni kullanıcı için eğitim planı"""
        # Kullanıcı otomatik oluşturulmalı
        plan = manager.generate_training_plan("new_user")
        
        assert plan["user_id"] == "new_user"
        assert plan["current_phase"] == "Foundation"


class TestMultipleAttempts:
    """Birden fazla deneme senaryolarının testleri"""
    
    @pytest.fixture
    def temp_db(self):
        """Geçici veritabanı dosyası"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def manager(self, temp_db):
        return UserProgressManager(temp_db)
    
    def test_curb_up_scenario(self, manager):
        """Kaldırıma çıkma senaryosu"""
        user_id = "user_001"
        skill_id = "intermediate-curb-up-help"
        
        # İlk deneme - başarısız (yanlış input)
        attempt1 = manager.start_skill_attempt(user_id, skill_id)
        manager.record_step_input(attempt1, 1, "W", "W")  # Doğru
        manager.record_step_input(attempt1, 2, "SPACE", "SPACE")  # Doğru
        manager.record_step_input(attempt1, 3, "X", "W")  # Yanlış
        manager.record_step_error(
            attempt1, 3, "wrong_input",
            "pop_casters", "move_forward"
        )
        manager.complete_skill_attempt(attempt1, success=False)
        
        # İkinci deneme - başarılı
        attempt2 = manager.start_skill_attempt(user_id, skill_id)
        manager.record_step_input(attempt2, 1, "W", "W")
        manager.record_step_input(attempt2, 2, "SPACE", "SPACE")
        manager.record_step_input(attempt2, 3, "X", "X")
        manager.record_step_input(attempt2, 4, "V", "V")
        manager.record_step_input(attempt2, 5, "W", "W")
        manager.complete_skill_attempt(attempt2, success=True)
        
        # İstatistikleri kontrol et
        stats = manager.get_skill_stats(user_id, skill_id)
        assert stats["attempts"] == 2
        assert stats["successful_attempts"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["total_errors"] == 1
        
        # Zayıf adımları kontrol et
        weak_steps = manager.get_weak_steps(user_id, skill_id)
        assert len(weak_steps) == 1
        assert weak_steps[0]["step_number"] == 3


class TestConcurrency:
    """Eşzamanlılık testleri"""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    def test_multiple_active_attempts(self, temp_db):
        """Birden fazla aktif deneme"""
        manager = UserProgressManager(temp_db)
        
        # Aynı anda birden fazla deneme
        attempt1 = manager.start_skill_attempt("user_001", "skill_001")
        attempt2 = manager.start_skill_attempt("user_001", "skill_002")
        attempt3 = manager.start_skill_attempt("user_002", "skill_001")
        
        # Her biri ayrı olmalı
        assert attempt1 != attempt2 != attempt3
        
        # Her birine ayrı input kaydet
        manager.record_step_input(attempt1, 1, "W", "W")
        manager.record_step_input(attempt2, 1, "S", "S")
        manager.record_step_input(attempt3, 1, "A", "A")
        
        # Her birini tamamla
        manager.complete_skill_attempt(attempt1, success=True)
        manager.complete_skill_attempt(attempt2, success=False)
        manager.complete_skill_attempt(attempt3, success=True)
        
        # Kullanıcı 1'in istatistikleri
        stats1 = manager.get_skill_stats("user_001", "skill_001")
        stats2 = manager.get_skill_stats("user_001", "skill_002")
        
        assert stats1["attempts"] == 1
        assert stats1["successful_attempts"] == 1
        assert stats2["attempts"] == 1
        assert stats2["successful_attempts"] == 0


class TestGlobalAnalytics:
    """Global analytics tests"""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def manager(self, temp_db):
        return UserProgressManager(temp_db)
    
    def test_get_global_error_stats_empty(self, manager):
        """Global istatistikler - veri yokken"""
        stats = manager.get_global_error_stats()
        
        assert stats["total_attempts"] == 0
        assert stats["total_users"] == 0
        assert len(stats["skill_summary"]) == 0
        assert len(stats["problematic_steps"]) == 0
        assert len(stats["action_confusion"]) == 0
    
    def test_get_global_error_stats_with_data(self, manager):
        """Global istatistikler - veri ile"""
        # Birden fazla kullanıcı ve deneme oluştur
        for user_num in range(3):
            user_id = f"user_{user_num}"
            
            # Skill 1 - bazı hatalar
            for _ in range(2):
                attempt = manager.start_skill_attempt(user_id, "skill_001")
                manager.record_step_error(
                    attempt, 1, "wrong_input",
                    "move_forward", "move_backward"
                )
                manager.complete_skill_attempt(attempt, success=False)
            
            # Skill 1 - başarılı
            attempt = manager.start_skill_attempt(user_id, "skill_001")
            manager.complete_skill_attempt(attempt, success=True)
            
            # Skill 2 - hatalar
            attempt = manager.start_skill_attempt(user_id, "skill_002")
            manager.record_step_error(
                attempt, 2, "wrong_direction",
                "turn_left", "turn_right"
            )
            manager.complete_skill_attempt(attempt, success=False)
        
        stats = manager.get_global_error_stats()
        
        # Toplam sayılar
        assert stats["total_attempts"] == 12  # 3 users * 4 attempts
        assert stats["total_users"] == 3
        
        # Skill summary
        assert len(stats["skill_summary"]) == 2
        skill_001_stats = next((s for s in stats["skill_summary"] if s["skill_id"] == "skill_001"), None)
        assert skill_001_stats is not None
        assert skill_001_stats["total_attempts"] == 9  # 3 users * 3 attempts
        assert skill_001_stats["failed_attempts"] == 6  # 3 users * 2 failed
        
        # Problematic steps
        assert len(stats["problematic_steps"]) > 0
        
        # Action confusion
        assert len(stats["action_confusion"]) > 0
        confusion = stats["action_confusion"][0]
        assert "expected" in confusion
        assert "actual" in confusion
        assert "count" in confusion
    
    def test_get_skill_error_stats(self, manager):
        """Skill-specific error stats"""
        # Birden fazla kullanıcı için hatalar oluştur
        for user_num in range(2):
            user_id = f"user_{user_num}"
            
            # Step 1'de hatalar
            for _ in range(3):
                attempt = manager.start_skill_attempt(user_id, "skill_001")
                manager.record_step_error(
                    attempt, 1, "wrong_input",
                    "move_forward", "move_backward"
                )
                manager.complete_skill_attempt(attempt, success=False)
            
            # Step 2'de hatalar
            for _ in range(1):
                attempt = manager.start_skill_attempt(user_id, "skill_001")
                manager.record_step_error(
                    attempt, 2, "wrong_direction",
                    "turn_left", "turn_right"
                )
                manager.complete_skill_attempt(attempt, success=False)
        
        stats = manager.get_skill_error_stats("skill_001")
        
        assert stats is not None
        assert stats["skill_id"] == "skill_001"
        assert stats["total_attempts"] == 8  # 2 users * 4 attempts
        
        # Step error rates
        assert len(stats["step_error_rates"]) == 2
        step_1_stats = next((s for s in stats["step_error_rates"] if s["step_number"] == 1), None)
        assert step_1_stats is not None
        assert step_1_stats["total_errors"] == 6  # 2 users * 3 errors
        
        # Most difficult step
        assert stats["most_difficult_step"] is not None
        assert stats["most_difficult_step"]["step_number"] == 1
    
    def test_get_skill_error_stats_not_found(self, manager):
        """Skill error stats - skill bulunamazsa"""
        stats = manager.get_skill_error_stats("nonexistent_skill")
        assert stats is None
    
    def test_clear_user_progress(self, manager):
        """Kullanıcı ilerleme verilerini silme"""
        # Kullanıcı oluştur ve ilerleme ekle
        user_id = "test_user"
        attempt = manager.start_skill_attempt(user_id, "skill_001")
        manager.record_step_error(
            attempt, 1, "wrong_input",
            "move_forward", "move_backward"
        )
        manager.complete_skill_attempt(attempt, success=False)
        
        # Kullanıcının verisi olmalı
        user = manager.get_user(user_id)
        assert len(user["skill_progress"]) > 0
        
        # İlerlemeyi sil
        success = manager.clear_user_progress(user_id)
        assert success is True
        
        # Veriler temizlenmeli
        user = manager.get_user(user_id)
        assert len(user["skill_progress"]) == 0
        assert len(user["sessions"]) == 0
        
        # Attempts silinmeli
        db = manager._load_db()
        user_attempts = [att for att in db.get("attempts", []) if att["user_id"] == user_id]
        assert len(user_attempts) == 0
    
    def test_clear_user_progress_not_found(self, manager):
        """Var olmayan kullanıcı ilerleme silme"""
        success = manager.clear_user_progress("nonexistent_user")
        assert success is False
    
    def test_get_skill_comparisons(self, manager):
        """Kullanıcı vs global performans karşılaştırması"""
        # Global veri oluştur - diğer kullanıcılar
        for user_num in range(3):
            other_user = f"other_user_{user_num}"
            # %50 başarı oranı
            for _ in range(5):
                attempt = manager.start_skill_attempt(other_user, "skill_001")
                manager.complete_skill_attempt(attempt, success=True)
            for _ in range(5):
                attempt = manager.start_skill_attempt(other_user, "skill_001")
                manager.complete_skill_attempt(attempt, success=False)
        
        # Test kullanıcısı - %80 başarı oranı
        test_user = "test_user"
        for _ in range(8):
            attempt = manager.start_skill_attempt(test_user, "skill_001")
            manager.complete_skill_attempt(attempt, success=True)
        for _ in range(2):
            attempt = manager.start_skill_attempt(test_user, "skill_001")
            manager.complete_skill_attempt(attempt, success=False)
        
        comparisons = manager.get_skill_comparisons(test_user)
        
        assert len(comparisons) == 1
        comp = comparisons[0]
        assert comp["skill_id"] == "skill_001"
        assert comp["your_success_rate"] == 0.8
        # Global: (15 success + 8 test) / (30 total + 10 test) = 23/40 = 0.575
        assert comp["global_success_rate"] > 0.5
        assert comp["comparison"] == "above_average"
    
    def test_enhanced_training_plan(self, manager):
        """Zenginleştirilmiş eğitim planı"""
        # Global veri oluştur
        for user_num in range(2):
            other_user = f"other_user_{user_num}"
            attempt = manager.start_skill_attempt(other_user, "skill_001")
            manager.record_step_error(
                attempt, 1, "wrong_direction",
                "move_forward", "move_backward"
            )
            manager.complete_skill_attempt(attempt, success=False)
        
        # Test kullanıcısı
        test_user = "test_user"
        attempt = manager.start_skill_attempt(test_user, "skill_001")
        manager.record_step_error(
            attempt, 1, "wrong_input",
            "move_forward", "turn_right"
        )
        manager.complete_skill_attempt(attempt, success=False)
        
        plan = manager.generate_training_plan(test_user)
        
        # Yeni alanlar mevcut olmalı
        assert "global_insights" in plan
        assert "your_common_errors" in plan
        assert "skill_comparisons" in plan
        
        # Global insights
        global_insights = plan["global_insights"]
        assert "most_failed_skills" in global_insights
        assert "common_mistakes" in global_insights
        assert "problematic_steps" in global_insights
        
        # Your common errors
        assert isinstance(plan["your_common_errors"], list)
        if len(plan["your_common_errors"]) > 0:
            error = plan["your_common_errors"][0]
            assert "skill_id" in error
            assert "step_number" in error
            assert "error_type" in error
        
        # Skill comparisons
        assert isinstance(plan["skill_comparisons"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
