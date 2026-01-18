"""
Profil komut handler'ları.
"""

from slack_bolt import App
from src.core.logger import logger
from src.commands import ChatManager
from src.repositories import UserRepository


def setup_profile_handlers(
    app: App,
    chat_manager: ChatManager,
    user_repo: UserRepository
):
    """Profil handler'larını kaydeder."""
    
    @app.command("/profilim")
    def handle_profile_command(ack, body):
        """Kullanıcının kendi kayıtlı bilgilerini gösterir."""
        ack()
        user_id = body["user_id"]
        channel_id = body["channel_id"]
        
        logger.info(f"[>] /profilim komutu geldi | Kullanıcı: {user_id} | Kanal: {channel_id}")
        
        try:
            user_data = user_repo.get_by_slack_id(user_id)
            
            if not user_data:
                chat_manager.post_ephemeral(
                    channel=channel_id,
                    user=user_id,
                    text="Henüz sistemde kaydın bulunmuyor. 😔 Lütfen yöneticinle iletişime geç."
                )
                return

            # Profil Kartı Oluştur (orta isim varsa dahil et)
            first_name = user_data.get('first_name', '')
            middle_name = user_data.get('middle_name', '')
            surname = user_data.get('surname', '')
            
            if middle_name:
                display_name = f"{first_name} {middle_name} {surname}".strip()
            else:
                display_name = f"{first_name} {surname}".strip()
            
            if not display_name:
                display_name = user_data.get('full_name', 'Bilinmiyor')
            
            text = (
                f"👤 *KİMLİK KARTI*\n"
                f"------------------\n"
                f"*Ad Soyad:* {display_name}\n"
                f"*Cohort:* {user_data.get('cohort', 'Belirtilmemiş')}\n"
                f"*Doğum Tarihi:* {user_data.get('birthday', 'Yok')}\n"
                f"------------------"
            )
            
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=text
            )
            logger.info(f"[+] Profil görüntülendi | Kullanıcı: {user_data.get('full_name', user_id)} ({user_id}) | Cohort: {user_data.get('cohort', 'Yok')}")
            
        except Exception as e:
            logger.error(f"[X] Profil görüntüleme hatası | Kullanıcı: {user_id} | Hata: {e}", exc_info=True)
            chat_manager.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text="Profil bilgilerine ulaşırken bir sorun yaşadım. 🤕"
            )
