import os
import random
import logging
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from database import get_poll_by_ts, get_poll_results, close_poll
from questions import QUESTION_POOL

logger = logging.getLogger("CommunityConnectBot.Scheduler")

# Hedef Kanal ID'si (Günün sorusu ve açılış mesajı için)
CHANNEL_ID = os.environ.get("SLACK_STARTUP_CHANNEL", "#general")

_global_scheduler = None

def send_daily_question(app):
    """
    Kanal'a rastgele bir soru gönderir.
    """
    question = random.choice(QUESTION_POOL)
    logger.info(f"Günün sorusu gönderiliyor: {question}")
    try:
        msg_text = f"🌟 *Topluluk İçin Günün Sorusu:*\n\n> {question}\n\nDüşüncelerinizi paylaşarak sohbete katılın! ✨"
        app.client.chat_postMessage(
            channel=CHANNEL_ID,
            text=f"Günün Sorusu: {question}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": msg_text
                    }
                }
            ]
        )
        logger.info("Soru başarıyla gönderildi.")
    except Exception as e:
        logger.error(f"Soru gönderilirken hata oluştu: {e}")

def start_scheduler(app):
    """
    Zamanlayıcıyı başlatır ve görevleri ekler.
    """
    global _global_scheduler
    logger.info("Zamanlayıcı kurulumu yapılıyor...")
    _global_scheduler = BackgroundScheduler()
    
    # Günün sorusu: Her gün saat 10:00
    _global_scheduler.add_job(send_daily_question, 'cron', hour=10, minute=0, args=[app])
    
    _global_scheduler.start()
    logger.info("📅 Zamanlayıcı başlatıldı.")

def schedule_poll_close(app, message_ts, minutes):
    """
    Belirli bir süre sonra oylamayı kapatacak görevi planlar.
    """
    global _global_scheduler
    if _global_scheduler:
        run_at = datetime.now() + timedelta(minutes=minutes)
        _global_scheduler.add_job(
            close_poll_task, 
            'date', 
            run_date=run_at, 
            args=[app, message_ts],
            id=f"close_{message_ts}"
        )
        logger.info(f"Oylama kapatma görevi planlandı: {message_ts} ({minutes} dk sonra)")

def close_poll_task(app, message_ts):
    """
    Oylamayı kapatır ve sonuçları duyurur.
    """
    logger.info(f"Oylama kapatma tetiklendi: {message_ts}")
    
    poll = get_poll_by_ts(message_ts)
    if not poll or len(poll) < 5:
        return
        
    poll_id, topic, options_json, is_active, channel_id = poll
    if not is_active:
        return

    results = get_poll_results(poll_id)
    options = json.loads(options_json)
    close_poll(poll_id)

    # Sonuç mesajını hazırla
    result_text = f"⌛ *OYLAMA SONA ERDİ: {topic}*\n\n"
    max_votes = -1
    winners = []

    for i, opt in enumerate(options):
        count = results.get(i, 0)
        result_text += f"• {opt}: *{count} oy*\n"
        if count > max_votes:
            max_votes = count
            winners = [opt]
        elif count == max_votes and count > 0:
            winners.append(opt)

    if max_votes > 0:
        winner_str = ", ".join(winners)
        result_text += f"\n🏆 *Kazanan:* {winner_str}"
    else:
        result_text += "\n🤔 Hiç oy kullanılmadı."

    try:
        # Eski oylama mesajını sil
        app.client.chat_delete(channel=channel_id, ts=message_ts)
        logger.info(f"Orijinal oylama mesajı silindi: {message_ts}")
    except Exception as e:
        logger.warning(f"Oylama mesajı silinirken hata (mesaj zaten silinmiş olabilir): {e}")

    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f"Oylama Sonucu: {topic}",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": result_text}
                }
            ]
        )
        logger.info(f"Oylama sonuçları kanala gönderildi: {topic}")
    except Exception as e:
        logger.error(f"Oylama sonucu gönderilirken hata: {e}")
