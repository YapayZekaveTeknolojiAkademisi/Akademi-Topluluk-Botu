"""
Admin istatistik komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.commands import ChatManager
from src.services import StatisticsService
from src.repositories import UserRepository


def is_admin(app: App, user_id: str) -> bool:
    """Kullanıcının admin olup olmadığını kontrol eder."""
    try:
        res = app.client.users_info(user=user_id)
        if res["ok"]:
            user = res["user"]
            return user.get("is_admin", False) or user.get("is_owner", False)
    except Exception as e:
        logger.error(f"[X] Yetki kontrolü hatası: {e}")
    return False


def setup_statistics_handlers(
    app: App,
    statistics_service: StatisticsService,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Admin istatistik handler'larını kaydeder."""
    
    @app.command("/admin-istatistik")
    def handle_admin_statistics(ack, body):
        """Admin istatistiklerini gösterir (Sadece adminler)."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        
        # Kullanıcı bilgisini al
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            user_name = user_data.get('full_name', user_id) if user_data else user_id
        except Exception:
            user_name = user_id
        
        logger.info(f"[>] /admin-istatistik komutu geldi | Kullanıcı: {user_name} ({user_id})")
        
        # Admin kontrolü
        if not is_admin(app, user_id):
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="🚫 Bu komutu sadece adminler kullanabilir."
            )
            logger.warning(f"[!] Yetkisiz erişim denemesi | Kullanıcı: {user_name} ({user_id})")
            return
        
        try:
            # İstatistikleri topla
            stats = statistics_service.get_all_statistics()
            
            # Formatlanmış rapor oluştur
            report = statistics_service.format_statistics_report(stats)
            
            # Kullanıcıya gönder
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=report
            )
            
            logger.info(f"[+] İstatistikler gösterildi | Kullanıcı: {user_name} ({user_id})")
            
        except Exception as e:
            logger.error(f"[X] İstatistik hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="❌ İstatistikler alınırken bir hata oluştu. Lütfen logları kontrol edin."
            )
