import os
import re
import random
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import json
from datetime import datetime, timedelta
from scheduler import start_scheduler, schedule_poll_close
from database import init_db, import_csv_to_db, get_user, add_user, create_poll, add_vote, get_poll_by_ts, has_user_voted
from questions import ICE_BREAKER_QUESTIONS

# --- Renkli Logging Yapılandırması ---
class CustomFormatter(logging.Formatter):
    """ANSI Renk kodları ile log formatı"""
    
    blue = "\x1b[38;5;39m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    format_str = "%(asctime)s | %(levelname)s | %(message)s"

    FORMATS = {
        logging.DEBUG: blue + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

logger = logging.getLogger("CommunityConnectBot")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# Çevresel değişkenleri yükle (.env dosyasından)
load_dotenv()

# App tanımlaması
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# --- Global Hata Yönetimi ---
@app.error
def global_error_handler(error, body, logger):
    """
    Uygulama genelinde oluşabilecek beklenmedik hataları yakalar.
    """
    # Hata ayrıntılarını al
    error_msg = str(error)
    user_id = body.get("user", {}).get("id") or body.get("user_id", "Bilinmiyor")
    trigger = body.get("command") or body.get("action_id") or body.get("callback_id") or "N/A"
    
    # Loglara detaylı yaz
    logger.error(f"SİSTEM HATASI - Kullanıcı: {user_id} - Tetikleyici: {trigger} - Hata: {error_msg}")
    
    # Eğer bu bir slash komutu ise kullanıcıya nezaket mesajı gönder
    # Not: Bolt otomatik olarak ack() yapmaya çalışabilir ama güvenlik için try-except
    try:
        # Bazı durumlarda client'a erişim yetmeyebilir, bu yüzden basit bir kontrol
        pass 
    except:
        pass

def get_display_name(user_id, client):
    """
    Kullanıcının ismini önce veritabanından, yoksa Slack API'den çeker.
    """
    # 1. Veritabanını kontrol et
    user_data = get_user(user_id)
    if user_data:
        return f"{user_data[0]} {user_data[1]}", user_data[2] # isim soyisim, departman

    # 2. Slack API'yi kontrol et
    try:
        response = client.users_info(user=user_id)
        if response["ok"]:
            user_info = response["user"]
            real_name = user_info.get("real_name") or user_info.get("name")
            return real_name, None
    except Exception as e:
        logger.error(f"Slack API'den isim çekilemedi: {e}")
    
    return "Topluluk Üyemiz", None

def is_admin(user_id, client):
    """
    Kullanıcının admin veya owner olup olmadığını kontrol eder.
    """
    try:
        res = client.users_info(user=user_id)
        if res["ok"]:
            user = res["user"]
            return user.get("is_admin", False) or user.get("is_owner", False)
    except Exception as e:
        logger.error(f"Yetki kontrolü sırasında hata: {e}")
    return False

# --- 3. Özellik: Rastgele Kahve Eşleşmesi ---
COFFEE_WAITING_LIST = set()

@app.command("/kahve")
def handle_coffee_command(ack, body, client):
    """
    Kanala kahve daveti gönderir.
    """
    ack()
    user_id = body["user_id"]
    channel_id = body["channel_id"]
    
    try:
        user_name, dept_name = get_display_name(user_id, client)
        dept_info = f"({dept_name})" if dept_name else ""

        # Davet mesajını gönder
        client.chat_postMessage(
            channel=channel_id,
            text=f"☕ {user_name} kahve molası vermek istiyor!",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"☕ *{user_name}* {dept_info} topluluğumuzla kahve molası vermek istiyor! \nEşlik etmek ve keyifli bir sohbet başlatmak ister misin?"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Birlikte İçelim! ☕", "emoji": True},
                            "style": "primary",
                            "value": user_id,
                            "action_id": "join_coffee"
                        }
                    ]
                }
            ]
        )
        logger.info(f"Kahve Daveti - {user_name} ({user_id}) - Başarılı - Davet kanala gönderildi")
    except Exception as e:
        logger.error(f"Kahve Daveti - {user_id} - Hata: {e}")
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="❌ Davet oluşturulurken bir hata oluştu.")

@app.action("join_coffee")
def handle_join_coffee(ack, body, client):
    """
    Birisi davete tıkladığında eşleşmeyi gerçekleştirir.
    """
    ack()
    user2_id = body["user"]["id"] # Tıklayan kişi
    user1_id = body["actions"][0]["value"] # Daveti başlatan kişi
    channel_id = body["channel"]["id"]
    message_ts = body["container"]["message_ts"]

    # Kendisiyle eşleşmesini engelleyelim
    if user1_id == user2_id:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user2_id,
            text="Bu davete şimdilik sadece topluluk üyelerimiz katılabilir. Başka birinin eşlik etmesini bekleyelim. ✨"
        )
        return

    try:
        # İsimleri al
        u1_name, _ = get_display_name(user1_id, client)
        u2_name, _ = get_display_name(user2_id, client)

        # Mesajı güncelle (Daveti kapat)
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text="Kahve eşleşmesi tamamlandı! ✨",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *{u1_name}* ve *{u2_name}* kahve molasında buluştu! \nKeyifli paylaşımlar dileriz. ✨☕"
                    }
                }
            ]
        )

        # DM Grubu oluştur
        conv = client.conversations_open(users=[user1_id, user2_id])
        dm_channel = conv["channel"]["id"]
        
        # Buz kırıcı soru seç
        ice_breaker = random.choice(ICE_BREAKER_QUESTIONS)

        client.chat_postMessage(
            channel=dm_channel,
            text=f"Selamlar <@{user1_id}> ve <@{user2_id}>! 🎉\nHarika bir kahve molası başlıyor! Sohbeti başlatmak için minik bir soru önerimiz var:\n\n> *{ice_breaker}*"
        )
        logger.info(f"Kahve Eşleşme - SİSTEM - Başarılı - {u1_name} & {u2_name} eşleşti")

    except Exception as e:
        logger.error(f"Kahve Eşleşme Hatası - {e}")
        client.chat_postEphemeral(channel=channel_id, user=user2_id, text="⚠️ Eşleşme sırasında bir teknik hata oluştu.")

# --- Yeni Özellikler: Kişisel Bilgiler ---

@app.command("/my-id")
def handle_my_id(ack, body, client):
    """
    Kullanıcının Slack ID'sini sadece kendisine gösterir.
    """
    ack()
    user_id = body["user_id"]
    try:
        user_name, _ = get_display_name(user_id, client)
        
        client.chat_postEphemeral(channel=body["channel_id"], user=user_id, text=f"Senin Slack ID'n: `{user_id}`")
        logger.info(f"ID Sorgulama - {user_name} ({user_id}) - Başarılı - ID gönderildi")
    except Exception as e:
        logger.error(f"ID Sorgulama - {user_id} - Hata: {e}")
        client.chat_postEphemeral(channel=body["channel_id"], user=user_id, text="⚠️ Kimlik bilgisi alınırken bir hata oluştu.")

@app.command("/my-department")
def handle_my_department(ack, body, client):
    """
    Kullanıcının deparmanını veritabanından sorgular ve sadece kendine gösterir.
    """
    ack()
    user_id = body["user_id"]
    try:
        user_name, dept_name = get_display_name(user_id, client)
        
        if dept_name:
            msg = f"Merhaba {user_name.split()[0]}, kayıtlı departmanın: *{dept_name}*"
            res_status = "Başarılı"
            res_detail = f"Departman bulundu: {dept_name}"
        else:
            msg = f"Merhaba {user_name.split()[0]}, veritabanında sana ait bir departman kaydı bulamadım. 🧐 \n`/save-me [Ad] [Soyad] [Departman]` komutu ile kendini kaydedebilirsin!"
            res_status = "Uyarı"
            res_detail = "DB kaydı yok"
            
        client.chat_postEphemeral(channel=body["channel_id"], user=user_id, text=msg)
        logger.info(f"Departman Sorgulama - {user_name} ({user_id}) - {res_status} - {res_detail}")
    except Exception as e:
        logger.error(f"Departman Sorgulama - {user_id} - Hata: {e}")
        client.chat_postEphemeral(channel=body["channel_id"], user=user_id, text="⚠️ Departman bilgisi sorgulanırken bir hata oluştu.")

@app.command("/save-me")
def handle_register_user(ack, body, client):
    """
    Kullanıcının kendi bilgilerini veritabanına eklemesini sağlar.
    Format: /save-me [Ad] [Soyad] [Departman]
    """
    ack()
    user_id = body["user_id"]
    text = body.get("text", "").strip()
    
    try:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            client.chat_postEphemeral(
                channel=body["channel_id"],
                user=user_id,
                text="⚠️ Lütfen bilgileri şu formatta girin: `/save-me [Ad] [Soyad] [Departman]` \nÖrnek: `/save-me Cemil Yılmaz Yazılım`"
            )
            return

        name, surname, department = parts
        add_user(user_id, name, surname, department)
        
        client.chat_postEphemeral(
            channel=body["channel_id"],
            user=user_id,
            text=f"✅ Harika! Bilgilerin topluluk veritabanına kaydedildi.\n*Ad:* {name} {surname}\n*Departman:* {department}"
        )
        logger.info(f"Kullanıcı Kaydı - {name} {surname} ({user_id}) - Başarılı - Departman: {department}")
    except Exception as e:
        logger.error(f"Kullanıcı kaydı hatası - {user_id} - {e}")
        client.chat_postEphemeral(channel=body["channel_id"], user=user_id, text="❌ Kayıt işlemi sırasında bir hata oluştu.")

# --- Oylama Sistemi ---

@app.command("/oylama")
def handle_poll_command(ack, body, client):
    """
    Yeni bir oylama başlatır. Sadece adminler kullanabilir.
    Format: /oylama [Dakika] [Konu] | Seçenek1 | Seçenek2
    """
    ack()
    user_id = body["user_id"]
    channel_id = body["channel_id"]
    text = body.get("text", "").strip()

    # 1. Yetki Kontrolü
    if not is_admin(user_id, client):
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="🚫 Bu komutu sadece adminler kullanabilir.")
        return

    # 2. Parametre Ayrıştırma
    try:
        # /oylama 10 Bugün ne yiyelim? | Kebap | Pizza
        main_parts = text.split(maxsplit=1)
        if len(main_parts) < 2:
            raise ValueError("Eksik parametre")
        
        minutes = int(main_parts[0])
        content_parts = main_parts[1].split("|")
        
        if len(content_parts) < 3:
            raise ValueError("En az iki seçenek gerekli")
            
        topic = content_parts[0].strip()
        options = [opt.strip() for opt in content_parts[1:]]
        
        # 3. Blokları Oluştur
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"🗳️ *YENİ OYLAMA: {topic}*"}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Süre: {minutes} dakika | Başlatan: <@{user_id}>"}]
            }
        ]
        
        button_elements = []
        for i, opt in enumerate(options):
            button_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": opt},
                "value": str(i),
                "action_id": f"vote_{i}"
            })
            
        blocks.append({"type": "actions", "elements": button_elements})

        # 4. Mesajı Gönder
        res = client.chat_postMessage(channel=channel_id, text=f"Oylama: {topic}", blocks=blocks)
        message_ts = res["ts"]
        
        # 5. DB'ye Kaydet
        end_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        create_poll(channel_id, message_ts, user_id, topic, json.dumps(options), end_time)
        
        # 6. Kapanış Görevi Ekle
        schedule_poll_close(app, message_ts, minutes)
        
        logger.info(f"Oylama Başlatıldı - {user_id} - Konu: {topic} - Süre: {minutes}dk")

    except ValueError:
        client.chat_postEphemeral(
            channel=channel_id, 
            user=user_id, 
            text="⚠️ Hatalı format! Kullanım: `/oylama [Dakika] [Konu] | Seçenek 1 | Seçenek 2`"
        )
    except Exception as e:
        logger.error(f"Oylama başlatılırken hata: {e}")
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="❌ Oylama başlatılamadı.")

@app.action(re.compile(r"^vote_"))
def handle_vote_action(ack, body, client):
    """
    Butonlara tıklandığında oy kaydeder.
    """
    ack()
    user_id = body["user"]["id"]
    message_ts = body["container"]["message_ts"]
    option_index = int(body["actions"][0]["value"])
    
    poll = get_poll_by_ts(message_ts)
    if not poll:
        return
    
    poll_id, topic, options_json, is_active, poll_channel_id = poll
    
    if not is_active:
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user_id, text="⌛ Bu oylama sona erdi.")
        return

    # 1 Kullanıcı - 1 Oy Kontrolü
    if has_user_voted(poll_id, user_id):
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user_id, text="⚠️ Bu oylama için zaten oy kullandın. Oylamada sadece bir kez oy kullanabilirsin.")
        return

    options = json.loads(options_json)
    if add_vote(poll_id, user_id, option_index):
        client.chat_postEphemeral(
            channel=body["channel"]["id"], 
            user=user_id, 
            text=f"✅ Oyun kaydedildi: *{options[option_index]}*"
        )
    else:
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user_id, text="❌ Oy verirken bir hata oluştu.")

# --- Başlangıç ---
if __name__ == "__main__":
    print("\n" + "="*50)
    print("      CommunityConnect Bot Setup Sequence      ")
    print("="*50 + "\n")
    
    # Veritabanını başlat
    init_db()
    
    # CSV Import Sorusu
    setup_needed = input("Kullanıcı verilerini bir CSV dosyasından içe aktarmak istiyor musunuz? (e/h): ").lower()
    if setup_needed == 'e':
        csv_path = input("Lütfen .csv dosyasının tam yolunu girin: ").strip()
        if import_csv_to_db(csv_path):
            print("✔ Veriler başarıyla içe aktarıldı.")
        else:
            print("✖ CSV aktarımı başarısız oldu veya atlandı.")
    
    print("\nBot başlatılıyor...\n")
    logger.info("Bot süreçleri devreye alınıyor...")
    
    # Zamanlayıcıyı başlat
    start_scheduler(app)
    
    # Socket Mode ile uygulamayı başlat
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        logger.error("Hata: SLACK_APP_TOKEN .env dosyasında bulunamadı!")
    else:
        logger.info("Socket Mode Handler başlatılıyor...")
        # Merhaba Mesajı Gönder
        try:
            startup_channel = os.environ.get("SLACK_STARTUP_CHANNEL", "#general")
            startup_text = (
                "Merhabalar herkese! Ben Cemil, yeni uyandım ve görevimin başındayım. ☀️\n\n"
                "Topluluk etkileşimini artırmak için buradayım! İşte yapabileceklerim:\n"
                "• *Kahve Molası:* `/kahve` yazarak rastgele bir çalışma arkadaşınla eşleşebilirsin. ☕\n"
                "• *Hızlı Oylama:* `/oylama` ile (adminler) ekip içi anketler başlatabilir. 🗳️\n"
                "• *Profilini Güncelle:* `/save-me` ile departman ve iletişim bilgilerini kaydedebilirsin. 📝\n"
                "• *Bilgi Sorgula:* `/my-id` veya `/my-department` ile kayıtlı bilgilerini görebilirsin. 🔍\n\n"
                "Güzel bir gün dilerim! ✨🚀"
            )
            app.client.chat_postMessage(
                channel=startup_channel,
                text=startup_text
            )
            logger.info(f"Açılış mesajı {startup_channel} kanalına gönderildi.")
        except Exception as e:
            logger.error(f"Açılış mesajı gönderilirken hata: {e}")

        handler = SocketModeHandler(app, app_token)
        handler.start()
