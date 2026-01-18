"""
Rate limiter testleri.
"""

import pytest
import time
from src.core.rate_limiter import RateLimiter


class TestRateLimiter:
    """RateLimiter testleri."""
    
    def test_allowed_request(self):
        """İzin verilen istek."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        allowed, msg = limiter.is_allowed("user1")
        assert allowed is True
        assert msg is None
    
    def test_rate_limit_exceeded(self):
        """Rate limit aşımı."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # İlk 2 istek izin verilmeli
        assert limiter.is_allowed("user1")[0] is True
        assert limiter.is_allowed("user1")[0] is True
        
        # 3. istek reddedilmeli
        allowed, msg = limiter.is_allowed("user1")
        assert allowed is False
        assert msg is not None
        assert "saniye" in msg
    
    def test_different_users(self):
        """Farklı kullanıcılar için ayrı limitler."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Her kullanıcı için limit ayrı olmalı
        assert limiter.is_allowed("user1")[0] is True
        assert limiter.is_allowed("user2")[0] is True
        assert limiter.is_allowed("user1")[0] is True
        assert limiter.is_allowed("user2")[0] is True
        
        # Her ikisi de limit'e ulaştı
        assert limiter.is_allowed("user1")[0] is False
        assert limiter.is_allowed("user2")[0] is False
    
    def test_reset(self):
        """Rate limit sıfırlama."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        # Limit'e ulaş
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        assert limiter.is_allowed("user1")[0] is False
        
        # Reset
        limiter.reset("user1")
        assert limiter.is_allowed("user1")[0] is True
