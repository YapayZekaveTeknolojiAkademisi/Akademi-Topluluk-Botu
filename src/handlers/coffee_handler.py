"""
Kahve eşleşmesi komut handler'ları.
"""

import asyncio
from slack_bolt import App
from src.core.logger import logger
from src.core.settings import get_settings
from src.core.rate_limiter import get_rate_limiter
from src.commands import ChatManager
from src.services import CoffeeMatchService
from src.repositories import UserRepository


def setup_coffee_handlers(
    app: App,
    coffee_service: CoffeeMatchService,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Kahve handler'larını kaydeder."""
    settings = get_settings()
    rate_limiter = get_rate_limiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )
    
    @app.command("/kahve")
    async def handle_coffee_command(ack, body):
        """Kahve eşleşmesi isteği gönderir (Bekleme Havuzu Sistemi)."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        
        # Rate limiting kontrolü
        allowed, error_msg = rate_limiter.is_allowed(user_id)
        if not allowed:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=error_msg
            )
            return
        
        # Kullanıcı bilgisini al
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            user_name = user_data.get('full_name', user_id) if user_data else user_id
        except Exception as e:
            logger.warning(f"[!] Kullanıcı bilgisi alınamadı: {e}")
            user_name = user_id
        
        logger.info(f"[>] /kahve komutu geldi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id}")
        
        try:
            response_msg = await coffee_service.request_coffee(user_id, channel_id, user_name)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=response_msg
            )
        except Exception as e:
            logger.error(f"[X] Kahve isteği hatası | Kullanıcı: {user_name} ({user_id}) | Hata: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Kahve makinesinde ufak bir arıza var sanırım ☕😅 Lütfen birazdan tekrar dene."
            )
    
    @app.action("join_coffee")
    def handle_join_coffee(ack, body):
        """
        Eski sistem uyumluluğu için join_coffee action handler.
        Yeni sistemde kahve eşleşmesi otomatik bekleme havuzu ile çalışır.
        """
        ack()
        user_id = body["user"]["id"]
        channel_id = body["channel"]["id"]
        
        # Kullanıcı bilgisini al
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            user_name = user_data.get('full_name', user_id) if user_data else user_id
        except Exception:
            user_name = user_id
        
        logger.info(f"[>] join_coffee action tetiklendi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id}")
        
        # Yeni sistemde kahve eşleşmesi için /kahve komutunu kullanmasını söyle
        chat_manager.post_ephemeral(
            channel=channel_id,
            user=user_id,
            text="☕ Bu buton eski sistem için. Yeni kahve eşleşmesi için `/kahve` komutunu kullanabilirsiniz!"
        )
