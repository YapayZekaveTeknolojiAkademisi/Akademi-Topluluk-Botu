"""
Bilgi küpü (RAG) komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.core.settings import get_settings
from src.core.rate_limiter import get_rate_limiter
from src.core.validators import QuestionRequest
from src.commands import ChatManager
from src.services import KnowledgeService
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


def setup_knowledge_handlers(
    app: App,
    knowledge_service: KnowledgeService,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Bilgi küpü handler'larını kaydeder."""
    settings = get_settings()
    rate_limiter = get_rate_limiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window
    )
    
    @app.command("/sor")
    async def handle_ask_command(ack, body):
        """Bilgi küpünden soru sorar."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        question = body.get("text", "").strip()
        
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
        
        logger.info(f"[>] /sor komutu geldi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id} | Soru: {question[:100]}...")
        
        # Input validation
        if not question:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="🤔 Neyi merak ediyorsun? Örnek: `/sor Mentorluk başvuruları ne zaman?`"
            )
            return
        
        try:
            question_request = QuestionRequest(question=question)
        except ValueError as ve:
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=f"Soru formatı hatalı. Lütfen tekrar deneyin.\n\nHata: {str(ve)}"
            )
            return
        
        chat_manager.post_ephemeral(
            channel=channel_id,
            user=user_id,
            text="🔍 Bilgi küpümü tarıyorum, lütfen bekleyin..."
        )
        
        try:
            answer = await knowledge_service.ask_question(question_request.question, user_id)
            logger.info(f"[+] SORU CEVAPLANDI | Kullanıcı: {user_name} ({user_id}) | Soru: {question[:50]}... | Cevap uzunluğu: {len(answer)} karakter")
            
            # Cevabı sadece soran kişiye göster (ephemeral)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=f"*Soru:* {question}\n\n{answer}"
            )
        except Exception as e:
            logger.error(f"[X] Soru cevaplama hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Şu an hafızamı toparlamakta zorlanıyorum, birazdan tekrar sorar mısın? 🧠✨"
            )
    
    @app.command("/cemil-indeksle")
    async def handle_reindex_command(ack, body):
        """Bilgi küpünü yeniden indeksler (Admin)."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        
        # Kullanıcı bilgisini al
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            user_name = user_data.get('full_name', user_id) if user_data else user_id
        except Exception:
            user_name = user_id
        
        logger.info(f"[>] /cemil-indeksle komutu geldi | Kullanıcı: {user_name} ({user_id}) | Kanal: {channel_id}")
        
        # Admin kontrolü
        if not is_admin(app, user_id):
            logger.warning(f"[!] Yetkisiz indeksleme denemesi | Kullanıcı: {user_name} ({user_id})")
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="🚫 Bu komutu sadece adminler kullanabilir."
            )
            return
        
        chat_manager.post_ephemeral(
            channel=channel_id,
            user=user_id,
            text="⚙️ Bilgi küpü yeniden taranıyor..."
        )
        
        try:
            await knowledge_service.process_knowledge_base()
            logger.info(f"[+] BİLGİ KÜPÜ YENİDEN İNDEKLENDİ | Kullanıcı: {user_name} ({user_id})")
            chat_manager.post_message(
                channel=channel_id,
                text=f"✅ <@{user_id}> Bilgi küpü güncellendi! Cemil artık en güncel dökümanları biliyor."
            )
        except Exception as e:
            logger.error(f"[X] İndeksleme hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="İndeksleme sırasında bir hata oluştu. Lütfen logları kontrol edin."
            )
