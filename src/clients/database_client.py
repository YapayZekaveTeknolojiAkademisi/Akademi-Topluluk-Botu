import sqlite3
import uuid
import os
from typing import List, Dict, Any, Optional
from src.core.logger import logger
from src.core.exceptions import DatabaseError

class DatabaseClient:
    """
    Cemil Bot için merkezi veritabanı yönetim sınıfı.
    SQLite kullanır ve genişletilebilir tablo yapısına sahiptir.
    """

    def __init__(self, db_path: str = "data/cemil_bot.db"):
        self.db_path = db_path
        # Klasör yoksa oluştur
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        """SQLite bağlantısı döndürür."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Dict benzeri erişim için
            return conn
        except sqlite3.Error as e:
            logger.error(f"[X] Veritabanı bağlantı hatası: {e}")
            raise DatabaseError(f"Veritabanına bağlanılamadı: {e}")

    def init_db(self):
        """Tabloları hazırlar."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Kullanıcılar Tablosu (Users)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        gender TEXT,
                        slack_id TEXT UNIQUE,
                        full_name TEXT,
                        first_name TEXT,
                        middle_name TEXT,
                        surname TEXT,
                        email TEXT,
                        country_code TEXT,
                        phone_number TEXT,
                        birthday TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info("[i] Veritabanı ve 'users' tablosu hazır.")
        except sqlite3.Error as e:
            logger.error(f"[X] Veritabanı ilklendirme hatası: {e}")
            raise DatabaseError(f"Tablolar oluşturulamadı: {e}")

    def add_user(self, user_data: Dict[str, Any]) -> str:
        """
        Yeni bir kullanıcı ekler. ID otomatik olarak UUID ile oluşturulur.
        """
        user_id = str(uuid.uuid4())
        columns = ["id"] + list(user_data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = [user_id] + list(user_data.values())

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                conn.commit()
                logger.info(f"[+] Yeni kullanıcı kaydedildi: {user_data.get('full_name')} (ID: {user_id})")
                return user_id
        except sqlite3.IntegrityError:
            logger.warning(f"[!] Kullanıcı zaten kayıtlı (Slack ID: {user_data.get('slack_id')})")
            return ""
        except sqlite3.Error as e:
            logger.error(f"[X] Kullanıcı ekleme hatası: {e}")
            raise DatabaseError(f"Kullanıcı kaydedilemedi: {e}")

    def get_user_by_slack_id(self, slack_id: str) -> Optional[Dict[str, Any]]:
        """Slack ID ile kullanıcı bilgilerini getirir."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE slack_id = ?", (slack_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"[X] Kullanıcı sorgulama hatası: {e}")
            raise DatabaseError(f"Kullanıcı bulunamadı: {e}")

    def update_user(self, slack_id: str, update_data: Dict[str, Any]) -> bool:
        """Kullanıcı bilgilerini günceller."""
        set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
        values = list(update_data.values()) + [slack_id]

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                sql = f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE slack_id = ?"
                cursor.execute(sql, values)
                conn.commit()
                logger.info(f"[+] Kullanıcı güncellendi: {slack_id}")
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"[X] Kullanıcı güncelleme hatası: {e}")
            raise DatabaseError(f"Güncelleme başarısız: {e}")

    def list_all_users(self) -> List[Dict[str, Any]]:
        """Tüm kullanıcıları listeler."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"[X] Kullanıcı listeleme hatası: {e}")
            raise DatabaseError(f"Liste alınamadı: {e}")
