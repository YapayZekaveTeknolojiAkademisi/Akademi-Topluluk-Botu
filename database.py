import sqlite3
import csv
import os
import logging

logger = logging.getLogger("CommunityConnectBot.Database")

DB_NAME = "community_bot.db"

def init_db():
    """
    Veritabanını ve gerekli tabloları oluşturur.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Kullanıcılar tablosunu oluştur
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                surname TEXT,
                slack_id TEXT UNIQUE NOT NULL,
                department TEXT
            )
        ''')
        
        # Slack ID üzerine index ekle
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_slack_id ON users (slack_id)')
        
        # Oylamalar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                message_ts TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                options TEXT NOT NULL, -- JSON string of options
                end_time DATETIME NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Oylar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                poll_id INTEGER,
                user_id TEXT,
                option_index INTEGER,
                PRIMARY KEY (poll_id, user_id),
                FOREIGN KEY (poll_id) REFERENCES polls(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"SQLite veritabanı hazırlandı: {DB_NAME}")
    except Exception as e:
        logger.error(f"Veritabanı başlatılırken hata oluştu: {e}")

def add_user(slack_id, name=None, surname=None, department=None):
    """
    Yeni bir kullanıcı ekler veya mevcut kullanıcıyı günceller.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (name, surname, slack_id, department)
            VALUES (?, ?, ?, ?)
        ''', (name, surname, slack_id, department))
        conn.commit()
        conn.close()
        logger.info(f"Kullanıcı veritabanına eklendi/güncellendi: {slack_id}")
    except Exception as e:
        logger.error(f"Kullanıcı eklenirken hata: {e}")

def import_csv_to_db(csv_path):
    """
    CSV dosyasını okur ve veritabanına aktarır.
    Beklenen CSV formatı (Başlıklar dahil): name,surname,slack_id,department
    """
    if not os.path.exists(csv_path):
        logger.error(f"Hata: Dosya bulunamadı: {csv_path}")
        return False

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cursor.execute('''
                    INSERT OR REPLACE INTO users (name, surname, slack_id, department)
                    VALUES (?, ?, ?, ?)
                ''', (row['name'], row['surname'], row['slack_id'], row['department']))
                count += 1
        
        conn.commit()
        conn.close()
        logger.info(f"CSV başarıyla içe aktarıldı. Toplam {count} kullanıcı eklendi.")
        return True
    except Exception as e:
        logger.error(f"CSV içe aktarılırken hata oluştu: {e}")
        return False

def get_user(slack_id):
    """
    Slack ID'ye göre kullanıcı bilgilerini getirir.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT name, surname, department FROM users WHERE slack_id = ?', (slack_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Kullanıcı sorgulanırken hata: {e}")
        return None

# --- Oylama İşlemleri ---

def create_poll(channel_id, message_ts, creator_id, topic, options_json, end_time):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO polls (channel_id, message_ts, creator_id, topic, options, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (channel_id, message_ts, creator_id, topic, options_json, end_time))
        poll_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return poll_id
    except Exception as e:
        logger.error(f"Oylama oluşturulurken hata: {e}")
        return None

def add_vote(poll_id, user_id, option_index):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO votes (poll_id, user_id, option_index)
            VALUES (?, ?, ?)
        ''', (poll_id, user_id, option_index))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Oy eklenirken hata: {e}")
        return False

def has_user_voted(poll_id, user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM votes WHERE poll_id = ? AND user_id = ?', (poll_id, user_id))
        voted = cursor.fetchone() is not None
        conn.close()
        return voted
    except Exception as e:
        logger.error(f"Oy kontrolü sırasında hata: {e}")
        return False

def get_poll_results(poll_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT option_index, COUNT(*) FROM votes WHERE poll_id = ? GROUP BY option_index', (poll_id,))
        results = dict(cursor.fetchall())
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Oylama sonuçları alınırken hata: {e}")
        return {}

def close_poll(poll_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE polls SET is_active = 0 WHERE id = ?', (poll_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Oylama kapatılırken hata: {e}")
        return False

def get_active_polls():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id, channel_id, message_ts, topic, options, end_time FROM polls WHERE is_active = 1')
        active_polls = cursor.fetchall()
        conn.close()
        return active_polls
    except Exception as e:
        logger.error(f"Aktif oylamalar alınırken hata: {e}")
        return []

def get_poll_by_ts(message_ts):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id, topic, options, is_active, channel_id FROM polls WHERE message_ts = ?', (message_ts,))
        poll = cursor.fetchone()
        conn.close()
        return poll
    except Exception as e:
        logger.error(f"Oylama sorgulanırken hata: {e}")
        return None
