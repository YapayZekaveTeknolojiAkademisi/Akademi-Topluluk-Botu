"""
Admin istatistik servisi.
"""

from typing import Dict, Any
from src.core.logger import logger
from src.repositories import (
    UserRepository,
    MatchRepository,
    HelpRepository,
    FeedbackRepository,
    PollRepository,
    VoteRepository
)


class StatisticsService:
    """
    Bot istatistiklerini toplayan ve raporlayan servis.
    """
    
    def __init__(
        self,
        user_repo: UserRepository,
        match_repo: MatchRepository,
        help_repo: HelpRepository,
        feedback_repo: FeedbackRepository,
        poll_repo: PollRepository,
        vote_repo: VoteRepository
    ):
        self.user_repo = user_repo
        self.match_repo = match_repo
        self.help_repo = help_repo
        self.feedback_repo = feedback_repo
        self.poll_repo = poll_repo
        self.vote_repo = vote_repo
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """
        Tüm istatistikleri toplar ve döndürür.
        
        Returns:
            Dict with all statistics
        """
        try:
            stats = {
                "users": self._get_user_statistics(),
                "matches": self._get_match_statistics(),
                "help_requests": self._get_help_statistics(),
                "feedbacks": self._get_feedback_statistics(),
                "polls": self._get_poll_statistics()
            }
            logger.info("[+] İstatistikler toplandı")
            return stats
        except Exception as e:
            logger.error(f"[X] StatisticsService.get_all_statistics hatası: {e}", exc_info=True)
            return {}
    
    def _get_user_statistics(self) -> Dict[str, Any]:
        """Kullanıcı istatistiklerini getirir."""
        try:
            all_users = self.user_repo.list()
            total_users = len(all_users)
            
            # Cohort bazlı dağılım
            cohort_distribution = {}
            for user in all_users:
                cohort = user.get("cohort", "Belirtilmemiş")
                cohort_distribution[cohort] = cohort_distribution.get(cohort, 0) + 1
            
            return {
                "total": total_users,
                "cohort_distribution": cohort_distribution
            }
        except Exception as e:
            logger.error(f"[X] User statistics hatası: {e}")
            return {"total": 0, "cohort_distribution": {}}
    
    def _get_match_statistics(self) -> Dict[str, Any]:
        """Kahve eşleşme istatistiklerini getirir."""
        try:
            all_matches = self.match_repo.list()
            total_matches = len(all_matches)
            
            active_matches = len([m for m in all_matches if m.get("status") == "active"])
            closed_matches = len([m for m in all_matches if m.get("status") == "closed"])
            
            return {
                "total": total_matches,
                "active": active_matches,
                "closed": closed_matches
            }
        except Exception as e:
            logger.error(f"[X] Match statistics hatası: {e}")
            return {"total": 0, "active": 0, "closed": 0}
    
    def _get_help_statistics(self) -> Dict[str, Any]:
        """Yardım isteği istatistiklerini getirir."""
        try:
            all_help = self.help_repo.list()
            total_help = len(all_help)
            
            open_help = len([h for h in all_help if h.get("status") == "open"])
            in_progress_help = len([h for h in all_help if h.get("status") == "in_progress"])
            resolved_help = len([h for h in all_help if h.get("status") == "resolved"])
            closed_help = len([h for h in all_help if h.get("status") == "closed"])
            
            return {
                "total": total_help,
                "open": open_help,
                "in_progress": in_progress_help,
                "resolved": resolved_help,
                "closed": closed_help
            }
        except Exception as e:
            logger.error(f"[X] Help statistics hatası: {e}")
            return {"total": 0, "open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
    
    def _get_feedback_statistics(self) -> Dict[str, Any]:
        """Geri bildirim istatistiklerini getirir."""
        try:
            all_feedbacks = self.feedback_repo.list()
            total_feedbacks = len(all_feedbacks)
            
            # Kategori bazlı dağılım
            category_distribution = {}
            for feedback in all_feedbacks:
                category = feedback.get("category", "general")
                category_distribution[category] = category_distribution.get(category, 0) + 1
            
            return {
                "total": total_feedbacks,
                "category_distribution": category_distribution
            }
        except Exception as e:
            logger.error(f"[X] Feedback statistics hatası: {e}")
            return {"total": 0, "category_distribution": {}}
    
    def _get_poll_statistics(self) -> Dict[str, Any]:
        """Oylama istatistiklerini getirir."""
        try:
            all_polls = self.poll_repo.list()
            total_polls = len(all_polls)
            
            open_polls = len([p for p in all_polls if p.get("is_closed", 0) == 0])
            closed_polls = len([p for p in all_polls if p.get("is_closed", 0) == 1])
            
            # Toplam oy sayısı
            all_votes = self.vote_repo.list()
            total_votes = len(all_votes)
            
            return {
                "total": total_polls,
                "open": open_polls,
                "closed": closed_polls,
                "total_votes": total_votes
            }
        except Exception as e:
            logger.error(f"[X] Poll statistics hatası: {e}")
            return {"total": 0, "open": 0, "closed": 0, "total_votes": 0}
    
    def format_statistics_report(self, stats: Dict[str, Any]) -> str:
        """
        İstatistikleri formatlanmış bir rapor olarak döndürür.
        
        Args:
            stats: get_all_statistics() tarafından döndürülen istatistikler
            
        Returns:
            Formatlanmış rapor metni
        """
        if not stats:
            return "❌ İstatistikler alınamadı."
        
        report = "📊 *CEMIL BOT İSTATİSTİKLERİ*\n\n"
        
        # Kullanıcı İstatistikleri
        users = stats.get("users", {})
        report += f"👥 *Kullanıcılar:*\n"
        report += f"   • Toplam: {users.get('total', 0)} kullanıcı\n"
        cohort_dist = users.get("cohort_distribution", {})
        if cohort_dist:
            report += f"   • Cohort Dağılımı:\n"
            for cohort, count in sorted(cohort_dist.items(), key=lambda x: x[1], reverse=True):
                report += f"     - {cohort}: {count} kişi\n"
        report += "\n"
        
        # Eşleşme İstatistikleri
        matches = stats.get("matches", {})
        report += f"☕ *Kahve Eşleşmeleri:*\n"
        report += f"   • Toplam: {matches.get('total', 0)} eşleşme\n"
        report += f"   • Aktif: {matches.get('active', 0)} eşleşme\n"
        report += f"   • Tamamlanan: {matches.get('closed', 0)} eşleşme\n"
        report += "\n"
        
        # Yardım İstekleri
        help_req = stats.get("help_requests", {})
        report += f"🆘 *Yardım İstekleri:*\n"
        report += f"   • Toplam: {help_req.get('total', 0)} istek\n"
        report += f"   • Açık: {help_req.get('open', 0)} istek\n"
        report += f"   • Devam Eden: {help_req.get('in_progress', 0)} istek\n"
        report += f"   • Çözülen: {help_req.get('resolved', 0)} istek\n"
        report += f"   • Kapatılan: {help_req.get('closed', 0)} istek\n"
        report += "\n"
        
        # Geri Bildirimler
        feedbacks = stats.get("feedbacks", {})
        report += f"📮 *Geri Bildirimler:*\n"
        report += f"   • Toplam: {feedbacks.get('total', 0)} geri bildirim\n"
        category_dist = feedbacks.get("category_distribution", {})
        if category_dist:
            report += f"   • Kategori Dağılımı:\n"
            for category, count in sorted(category_dist.items(), key=lambda x: x[1], reverse=True):
                report += f"     - {category}: {count} adet\n"
        report += "\n"
        
        # Oylamalar
        polls = stats.get("polls", {})
        report += f"🗳️ *Oylamalar:*\n"
        report += f"   • Toplam: {polls.get('total', 0)} oylama\n"
        report += f"   • Açık: {polls.get('open', 0)} oylama\n"
        report += f"   • Kapalı: {polls.get('closed', 0)} oylama\n"
        report += f"   • Toplam Oy: {polls.get('total_votes', 0)} oy\n"
        
        return report
