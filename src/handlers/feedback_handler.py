"""
Geri bildirim komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.core.settings import get_settings
from src.core.rate_limiter import get_rate_limiter
from src.core.validators import FeedbackRequest
from src.commands import ChatManager
from src.services import FeedbackService
from src.repositories import UserRepository


def setup_feedback_handlers(
    app: App,
    feedback_service: FeedbackService,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Geri bildirim handler'larını kaydeder."""
    settings = get_settings()
    rate_limiter = get_rate_limiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )
    
    @app.command("/geri-bildirim")
    async def handle_feedback_command(ack, body):
        """Anonim geri bildirim gönderir."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        text = body.get("text", "").strip()
        
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
        except Exception:
            user_name = user_id
        
        logger.info(f"[>] /geri-bildirim komutu geldi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id}")
        
        # Input validation
        if not text:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="🤔 Hangi konuda geri bildirim vermek istersin? Örnek: `/geri-bildirim genel Harika bir topluluk!`"
            )
            return
        
        try:
            feedback_request = FeedbackRequest.parse_from_text(text)
        except ValueError as ve:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=f"Geri bildirim formatı hatalı. Lütfen tekrar deneyin.\n\nHata: {str(ve)}"
            )
            return
        
        # Geri bildirim gönder
        try:
            await feedback_service.submit_feedback(feedback_request.content, feedback_request.category)
            
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="✅ Geri bildiriminiz anonim olarak iletildi. Teşekkürler!"
            )
            logger.info(f"[+] GERİ BİLDİRİM ALINDI | Kullanıcı: {user_name} ({user_id}) | Kategori: {feedback_request.category} | Uzunluk: {len(feedback_request.content)} karakter")
        except Exception as e:
            logger.error(f"[X] Geri bildirim gönderme hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Geri bildirim gönderilirken bir hata oluştu. Lütfen tekrar deneyin."
            )
