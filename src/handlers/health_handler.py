"""
Health check komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.commands import ChatManager
from src.clients import DatabaseClient, GroqClient, VectorClient


def check_database(db_client: DatabaseClient) -> tuple[bool, str]:
    """Veritabanı bağlantısını kontrol eder."""
    try:
        with db_client.get_connection() as conn:
            conn.execute("SELECT 1")
        return True, "✅ Veritabanı bağlantısı aktif"
    except Exception as e:
        logger.error(f"[X] Database health check hatası: {e}")
        return False, f"❌ Veritabanı hatası: {str(e)[:50]}"


def check_groq_api(groq_client: GroqClient) -> tuple[bool, str]:
    """Groq API bağlantısını kontrol eder."""
    try:
        # Basit bir test sorgusu yapabiliriz (async olduğu için şimdilik sadece client kontrolü)
        if groq_client.client:
            return True, "✅ Groq API client hazır"
        return False, "❌ Groq API client bulunamadı"
    except Exception as e:
        logger.error(f"[X] Groq API health check hatası: {e}")
        return False, f"❌ Groq API hatası: {str(e)[:50]}"


def check_vector_store(vector_client: VectorClient) -> tuple[bool, str]:
    """Vector store'u kontrol eder."""
    try:
        if hasattr(vector_client, 'documents') and vector_client.documents:
            doc_count = len(vector_client.documents)
            return True, f"✅ Vector store aktif ({doc_count} doküman)"
        return True, "✅ Vector store hazır (boş)"
    except Exception as e:
        logger.error(f"[X] Vector store health check hatası: {e}")
        return False, f"❌ Vector store hatası: {str(e)[:50]}"


def setup_health_handlers(
    app: App,
    chat_manager: ChatManager,
    db_client: DatabaseClient,
    groq_client: GroqClient,
    vector_client: VectorClient
):
    """Health check handler'larını kaydeder."""
    
    @app.command("/cemil-health")
    def handle_health_check(ack, body):
        """Bot sağlık durumunu kontrol eder."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        
        logger.info(f"[>] /cemil-health komutu geldi | Kullanıcı: {user_id}")
        
        try:
            # Tüm servisleri kontrol et
            db_status, db_msg = check_database(db_client)
            groq_status, groq_msg = check_groq_api(groq_client)
            vector_status, vector_msg = check_vector_store(vector_client)
            
            # Genel durum
            all_healthy = db_status and groq_status and vector_status
            status_icon = "✅" if all_healthy else "⚠️"
            
            health_report = (
                f"{status_icon} *CEMIL BOT SAĞLIK RAPORU*\n\n"
                f"{db_msg}\n"
                f"{groq_msg}\n"
                f"{vector_msg}\n\n"
            )
            
            if all_healthy:
                health_report += "🎉 Tüm sistemler çalışıyor!"
            else:
                health_report += "⚠️ Bazı servislerde sorun var. Lütfen logları kontrol edin."
            
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=health_report
            )
            
            logger.info(f"[+] Health check tamamlandı | Kullanıcı: {user_id} | Durum: {'Sağlıklı' if all_healthy else 'Sorunlu'}")
            
        except Exception as e:
            logger.error(f"[X] Health check hatası: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="❌ Health check sırasında bir hata oluştu."
            )
