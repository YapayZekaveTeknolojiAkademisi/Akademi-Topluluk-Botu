"""
Rate limiting için middleware ve utility sınıfları.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from src.core.logger import logger


class RateLimiter:
    """
    Kullanıcı bazlı rate limiting yönetimi.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: Zaman penceresi içinde izin verilen maksimum istek sayısı
            window_seconds: Zaman penceresi (saniye)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        Kullanıcının isteği yapıp yapamayacağını kontrol eder.
        
        Returns:
            (izin_var_mı, hata_mesajı veya None)
        """
        now = datetime.now()
        user_requests = self.requests[user_id]
        
        # Eski istekleri temizle (zaman penceresi dışındakiler)
        cutoff_time = now - timedelta(seconds=self.window_seconds)
        user_requests[:] = [req_time for req_time in user_requests 
                           if req_time > cutoff_time]
        
        # Rate limit kontrolü
        if len(user_requests) >= self.max_requests:
            oldest_request = min(user_requests) if user_requests else now
            wait_seconds = int((oldest_request + timedelta(seconds=self.window_seconds) - now).total_seconds())
            return False, f"⏳ Çok fazla istek! Lütfen {wait_seconds} saniye sonra tekrar deneyin."
        
        # İsteği kaydet
        user_requests.append(now)
        return True, None
    
    def reset(self, user_id: str):
        """Kullanıcının rate limit kayıtlarını sıfırla."""
        if user_id in self.requests:
            del self.requests[user_id]
    
    def cleanup_old_entries(self):
        """Eski kayıtları temizle (memory leak önleme)."""
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=self.window_seconds * 2)
        
        users_to_remove = []
        for user_id, requests in self.requests.items():
            # Eğer tüm istekler çok eskiyse, kullanıcıyı listeden çıkar
            if requests and max(requests) < cutoff_time:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.requests[user_id]
        
        if users_to_remove:
            logger.debug(f"[i] Rate limiter temizlendi: {len(users_to_remove)} kullanıcı kaldırıldı")


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(max_requests: int = 10, window_seconds: int = 60) -> RateLimiter:
    """Rate limiter singleton instance döndürür."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(max_requests, window_seconds)
    return _global_rate_limiter
