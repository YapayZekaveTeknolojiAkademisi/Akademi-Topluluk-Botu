import os
import asyncio
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from src.core.logger import logger
from src.core.exceptions import CemilBotError
from src.commands import ChatManager, ConversationManager
from src.clients import GroqClient, CronClient
from src.repositories import MatchRepository

class CoffeeMatchService:
    """
    Kullanıcılar arasında kahve eşleşmesi ve moderasyonunu yöneten servis.
    Bekleme havuzu (waiting pool) sistemi ile akıllı eşleştirme yapar.
    """

    def __init__(
        self, 
        chat_manager: ChatManager, 
        conv_manager: ConversationManager, 
        groq_client: GroqClient, 
        cron_client: CronClient,
        match_repo: MatchRepository
    ):
        self.chat = chat_manager
        self.conv = conv_manager
        self.groq = groq_client
        self.cron = cron_client
        self.match_repo = match_repo
        self.admin_channel = os.environ.get("ADMIN_CHANNEL_ID")
        
        # Bekleme Havuzu ve Rate Limiting
        self.waiting_pool: List[str] = []  # Bekleyen kullanıcı ID'leri
        self.last_request_time: Dict[str, datetime] = {}  # user_id -> son istek zamanı
        self.pool_timeout_jobs: Dict[str, str] = {}  # user_id -> cron job_id

    def can_request_coffee(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        Kullanıcının kahve isteği yapıp yapamayacağını kontrol eder.
        Returns: (izin_var_mı, hata_mesajı)
        """
        # Rate limiting: 5 dakikada bir istek
        if user_id in self.last_request_time:
            elapsed = datetime.now() - self.last_request_time[user_id]
            if elapsed < timedelta(minutes=5):
                remaining = 5 - int(elapsed.total_seconds() / 60)
                return False, f"⏳ Bir sonraki kahve isteğinizi {remaining} dakika sonra yapabilirsiniz."
        
        # Zaten havuzda mı?
        if user_id in self.waiting_pool:
            return False, "⏳ Zaten kahve havuzunda bekliyorsunuz. Eşleşme için sabırlı olun!"
        
        return True, None

    async def request_coffee(self, user_id: str, channel_id: str) -> str:
        """
        Kullanıcının kahve isteğini işler.
        Returns: Kullanıcıya gösterilecek mesaj
        """
        # İzin kontrolü
        can_request, error_msg = self.can_request_coffee(user_id)
        if not can_request:
            return error_msg
        
        # Son istek zamanını kaydet
        self.last_request_time[user_id] = datetime.now()
        
        # Havuzda başka biri var mı?
        if self.waiting_pool:
            # Eşleşme yap!
            partner_id = self.waiting_pool.pop(0)
            
            # Partner'ın timeout job'ını iptal et
            if partner_id in self.pool_timeout_jobs:
                self.cron.remove_job(self.pool_timeout_jobs[partner_id])
                del self.pool_timeout_jobs[partner_id]
            
            # Eşleşmeyi başlat
            await self.start_match(user_id, partner_id)
            
            logger.info(f"[+] Kahve eşleşmesi: {user_id} & {partner_id}")
            return f"✅ Harika! Bir kahve arkadaşı bulduk. Özel sohbet kanalınız açılıyor... ☕"
        
        else:
            # Havuza ekle
            self.waiting_pool.append(user_id)
            
            # 5 dakika sonra havuzdan çıkar
            job_id = f"coffee_timeout_{user_id}"
            self.cron.add_once_job(
                func=self._timeout_user,
                delay_minutes=5,
                job_id=job_id,
                args=[user_id]
            )
            self.pool_timeout_jobs[user_id] = job_id
            
            logger.info(f"[i] Kullanıcı kahve havuzuna eklendi: {user_id}")
            return (
                "☕ Kahve isteğiniz alındı! \\n\\n"
                "5 dakika içinde başka biri de kahve isterse eşleşeceksiniz. \\n"
                "Eğer kimse çıkmazsa istek otomatik olarak iptal edilecek. ⏳"
            )

    def _timeout_user(self, user_id: str):
        """5 dakika içinde eşleşme olmayan kullanıcıyı havuzdan çıkarır."""
        if user_id in self.waiting_pool:
            self.waiting_pool.remove(user_id)
            logger.info(f"[i] Kullanıcı kahve havuzundan zaman aşımı ile çıkarıldı: {user_id}")
            
            # Kullanıcıya bilgi mesajı gönder (isteğe bağlı)
            # Not: Bu noktada channel_id bilgisine erişimimiz yok, 
            # bu yüzden DM göndermek için user_id kullanabiliriz
            try:
                dm_channel = self.conv.open_conversation(users=[user_id])
                self.chat.post_message(
                    channel=dm_channel["id"],
                    text="⏰ Kahve isteğiniz zaman aşımına uğradı. 5 dakika içinde eşleşme bulunamadı. Tekrar denemek isterseniz `/kahve` yazabilirsiniz!"
                )
            except Exception as e:
                logger.error(f"[X] Timeout mesajı gönderilemedi: {e}")
        
        # Cleanup
        if user_id in self.pool_timeout_jobs:
            del self.pool_timeout_jobs[user_id]

    async def start_match(self, user_id1: str, user_id2: str):
        """
        İki kullanıcıyı eşleştirir, grup açar ve buzları eritir.
        """
        try:
            logger.info(f"[>] Kahve eşleşmesi başlatılıyor: {user_id1} & {user_id2}")
            
            # 1. Grup konuşması aç
            channel = self.conv.open_conversation(users=[user_id1, user_id2])
            channel_id = channel["id"]
            logger.info(f"[+] Özel grup oluşturuldu: {channel_id}")

            # 2. Veritabanına kaydet
            match_id = self.match_repo.create({
                "channel_id": channel_id,
                "user1_id": user_id1,
                "user2_id": user_id2,
                "status": "active"
            })

            # 3. Ice Breaker mesajı oluştur
            system_prompt = (
                "Sen Cemil'sin, bir topluluk asistanısın. Görevin birbiriyle eşleşen iki iş arkadaşı için "
                "kısa, eğlenceli ve samimi bir tanışma mesajı yazmak. "
                "ÖNEMLİ: Hiçbir emoji veya ASCII olmayan karakter kullanma. "
                "Sadece ASCII (Harfler, sayılar ve [i], [c], [>], == gibi işaretler) kullan."
            )
            user_prompt = f"Şu iki kullanıcı az önce kahve için eşleşti: <@{user_id1}> ve <@{user_id2}>. Onlara güzel bir selam ver."
            
            ice_breaker = await self.groq.quick_ask(system_prompt, user_prompt)

            # 4. Mesajı kanala gönder
            self.chat.post_message(
                channel=channel_id,
                text=ice_breaker,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"[c] *Kahve Eşleşmesi:* \n\n{ice_breaker}"}
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "[i] Bu kanal 5 dakika sonra otomatik olarak kapatılacaktır."}]
                    }
                ]
            )

            # 5. 5 dakika sonra kapatma görevi planla
            self.cron.add_once_job(
                func=self.close_match,
                delay_minutes=5,
                job_id=f"close_match_{channel_id}",
                args=[channel_id, match_id]
            )
            logger.info(f"[i] 5 dakika sonra kapatma görevi planlandı: {channel_id}")

        except Exception as e:
            logger.error(f"[X] CoffeeMatchService.start_match hatası: {e}")
            raise CemilBotError(f"Eşleşme başlatılamadı: {e}")

    async def close_match(self, channel_id: str, match_id: str):
        """Sohbet özetini çıkarır, admini bilgilendirir ve grubu kapatır."""
        try:
            logger.info(f"[>] Eşleşme grubu özeti hazırlanıyor: {channel_id}")
            
            # 1. Sohbet geçmişini al
            messages = self.conv.get_history(channel_id=channel_id, limit=50)
            
            # 2. Mesajları temizle
            user_messages = []
            for msg in messages:
                if not msg.get("bot_id") and msg.get("type") == "message":
                    user_text = msg.get("text", "")
                    user_messages.append(f"Kullanıcı: {user_text}")

            conversation_text = "\n".join(user_messages) if user_messages else "Konuşma yapılmadı."

            # 3. LLM ile Özet Çıkar
            summary = "Eşleşme süresince herhangi bir konuşma gerçekleşmedi."
            if user_messages:
                system_prompt = "Sen bir analiz asistanısın. Sana sunulan sohbet geçmişini analiz et ve konuşulan konuları bir cümleyle özetle. Sadece ASCII karakterler kullan."
                summary = await self.groq.quick_ask(system_prompt, f"Sohbet Geçmişi:\n{conversation_text}")

            # 4. Veritabanını Güncelle
            self.match_repo.update(match_id, {
                "status": "closed",
                "summary": summary
            })

            # 5. Admin Kanalını Bilgilendir
            if self.admin_channel:
                match_data = self.match_repo.get(match_id)
                admin_msg = (
                    f"[!] *EŞLEŞME ÖZETİ RAPORU*\n"
                    f"== Kanal: {channel_id}\n"
                    f"== Katılımcılar: <@{match_data['user1_id']}> & <@{match_data['user2_id']}>\n"
                    f"== Özet: {summary}"
                )
                self.chat.post_message(channel=self.admin_channel, text=admin_msg)

            # 6. Kapanış mesajı gönder ve grubu kapat
            self.chat.post_message(
                channel=channel_id,
                text="[>] Süremiz doldu. Bu sohbet sona erdi. Görüşmek üzere!"
            )
            
            await asyncio.sleep(1)
            self.conv.close_conversation(channel_id=channel_id)
            logger.info(f"[+] Grup kapatıldı ve raporlandı: {channel_id}")

        except Exception as e:
            logger.error(f"[X] CoffeeMatchService.close_match hatası: {e}")
