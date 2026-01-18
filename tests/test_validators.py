"""
Input validation testleri.
"""

import pytest
from src.core.validators import PollRequest, FeedbackRequest, QuestionRequest


class TestPollRequest:
    """PollRequest validation testleri."""
    
    def test_valid_poll_request(self):
        """Geçerli oylama isteği."""
        request = PollRequest.parse_from_text("10 Bugün ne yiyelim? | Kebap | Pizza | Burger")
        assert request.minutes == 10
        assert request.topic == "Bugün ne yiyelim?"
        assert len(request.options) == 3
        assert "Kebap" in request.options
    
    def test_invalid_minutes(self):
        """Geçersiz dakika değeri."""
        with pytest.raises(ValueError, match="1-1440"):
            PollRequest.parse_from_text("0 Test | A | B")
        
        with pytest.raises(ValueError, match="1-1440"):
            PollRequest.parse_from_text("2000 Test | A | B")
    
    def test_insufficient_options(self):
        """Yetersiz seçenek sayısı."""
        with pytest.raises(ValueError, match="En az iki seçenek"):
            PollRequest.parse_from_text("10 Test | A")
    
    def test_too_many_options(self):
        """Çok fazla seçenek."""
        options = " | ".join([f"Seçenek {i}" for i in range(12)])
        with pytest.raises(ValueError, match="En fazla 10 seçenek"):
            PollRequest.parse_from_text(f"10 Test | {options}")


class TestFeedbackRequest:
    """FeedbackRequest validation testleri."""
    
    def test_valid_feedback(self):
        """Geçerli geri bildirim."""
        request = FeedbackRequest.parse_from_text("Harika bir bot!")
        assert request.content == "Harika bir bot!"
        assert request.category == "general"
    
    def test_feedback_with_category(self):
        """Kategori ile geri bildirim."""
        request = FeedbackRequest.parse_from_text("technical Bot çok yavaş")
        assert request.category == "technical"
        assert request.content == "Bot çok yavaş"
    
    def test_empty_feedback(self):
        """Boş geri bildirim."""
        with pytest.raises(ValueError):
            FeedbackRequest.parse_from_text("")


class TestQuestionRequest:
    """QuestionRequest validation testleri."""
    
    def test_valid_question(self):
        """Geçerli soru."""
        request = QuestionRequest(question="Mentorluk başvuruları ne zaman?")
        assert request.question == "Mentorluk başvuruları ne zaman?"
    
    def test_empty_question(self):
        """Boş soru."""
        with pytest.raises(ValueError):
            QuestionRequest(question="")
    
    def test_too_long_question(self):
        """Çok uzun soru."""
        long_question = "A" * 501
        with pytest.raises(ValueError, match="en fazla 500 karakter"):
            QuestionRequest(question=long_question)
