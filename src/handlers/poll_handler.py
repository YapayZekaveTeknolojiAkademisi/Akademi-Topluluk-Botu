"""
Oylama komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.core.settings import get_settings
from src.core.rate_limiter import get_rate_limiter
from src.core.validators import PollRequest
from src.commands import ChatManager
from src.services import VotingService
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


def setup_poll_handlers(
    app: App,
    voting_service: VotingService,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Oylama handler'larını kaydeder."""
    settings = get_settings()
    rate_limiter = get_rate_limiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )
    
    @app.command("/oylama")
    async def handle_poll_command(ack, body):
        """Yeni bir oylama başlatır (Sadece adminler)."""
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
        
        logger.info(f"[>] /oylama komutu geldi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id} | Parametreler: {text[:50]}...")
        
        # Admin kontrolü
        if not is_admin(app, user_id):
            logger.warning(f"[!] Yetkisiz oylama denemesi | Kullanıcı: {user_name} ({user_id})")
            chat_manager.post_ephemeral(
                channel=channel_id, 
                user=user_id, 
                text="🚫 Bu komutu sadece adminler kullanabilir."
            )
            return
        
        # Input validation
        try:
            poll_request = PollRequest.parse_from_text(text)
        except ValueError as ve:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=f"Eyvah, oylama formatı biraz karıştı! 📝 Şöyle dener misin:\n`/oylama [Dakika] [Konu] | Seçenek 1 | Seçenek 2`\n\nHata: {str(ve)}"
            )
            return
        
        # Oylama oluştur
        try:
            await voting_service.create_poll(
                channel_id,
                poll_request.topic,
                poll_request.options,
                user_id,
                allow_multiple=False,
                duration_minutes=poll_request.minutes
            )
            logger.info(f"[?] OYLAMA BAŞLATILDI | Kullanıcı: {user_name} ({user_id}) | Konu: {poll_request.topic} | Süre: {poll_request.minutes}dk | Seçenekler: {len(poll_request.options)} adet")
        except Exception as e:
            logger.error(f"[X] Oylama başlatma hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Oylama oluşturulurken bir hata oluştu. Lütfen tekrar deneyin."
            )
    
    @app.action("poll_vote_0")
    @app.action("poll_vote_1")
    @app.action("poll_vote_2")
    @app.action("poll_vote_3")
    @app.action("poll_vote_4")
    def handle_poll_vote(ack, body):
        """Oylama butonlarına tıklamayı işler."""
        ack()
        user_id = body["user"]["id"]
        action_id = body["actions"][0]["action_id"]
        value = body["actions"][0]["value"]
        channel_id = body["channel"]["id"]
        
        # Kullanıcı bilgisini al
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            user_name = user_data.get('full_name', user_id) if user_data else user_id
        except Exception:
            user_name = user_id
        
        # value formatı: vote_{poll_id}_{option_index}
        parts = value.split("_")
        if len(parts) != 3:
            logger.warning(f"[!] Geçersiz oy formatı: {value}")
            return
        
        try:
            poll_id = parts[1]
            option_index = int(parts[2])
        except (ValueError, IndexError) as e:
            logger.warning(f"[!] Oy parse hatası: {e}")
            return
        
        logger.info(f"[>] OY VERİLDİ | Kullanıcı: {user_name} ({user_id}) | Oylama ID: {poll_id} | Seçenek: {option_index}")
        
        try:
            result = voting_service.cast_vote(poll_id, user_id, option_index)
            
            if result.get("success"):
                logger.info(f"[+] OY KAYDEDİLDİ | Kullanıcı: {user_name} ({user_id}) | Oylama ID: {poll_id} | Seçenek: {option_index}")
            else:
                logger.warning(f"[!] OY KAYDEDİLEMEDİ | Kullanıcı: {user_name} ({user_id}) | Oylama ID: {poll_id} | Sebep: {result.get('message', 'Bilinmiyor')}")
            
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=result["message"]
            )
        except Exception as e:
            logger.error(f"[X] Oy verme hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Oy verilirken bir hata oluştu. Lütfen tekrar deneyin."
            )
