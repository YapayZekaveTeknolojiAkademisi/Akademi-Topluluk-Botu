from typing import Dict, Any
from src.repositories.base_repository import BaseRepository
from src.clients.database_client import DatabaseClient
from src.core.logger import logger


class UserChallengeStatsRepository(BaseRepository):
    """Kullanıcı challenge istatistikleri için veritabanı erişim sınıfı."""

    def __init__(self, db_client: DatabaseClient):
        # BaseRepository'yi sadece table_name ve db_client için kullanıyoruz.
        super().__init__(db_client, "user_challenge_stats")

    def get_or_create(self, user_id: str) -> Dict[str, Any]:
        """
        Kullanıcı istatistiklerini getirir, yoksa oluşturur.
        NOT: Bu tabloda primary key 'user_id' olduğundan, BaseRepository.get kullanılmaz.
        """
        try:
            with self.db_client.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT * FROM {self.table_name} WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()

                if not row:
                    cursor.execute(
                        f"""
                        INSERT INTO {self.table_name} 
                        (user_id, total_challenges, completed_challenges, total_points)
                        VALUES (?, 0, 0, 0)
                        """,
                        (user_id,),
                    )
                    conn.commit()
                    cursor.execute(
                        f"SELECT * FROM {self.table_name} WHERE user_id = ?",
                        (user_id,),
                    )
                    row = cursor.fetchone()

                return dict(row) if row else {
                    "user_id": user_id,
                    "total_challenges": 0,
                    "completed_challenges": 0,
                    "total_points": 0,
                }
        except Exception as e:
            logger.error(f"[X] user_challenge_stats.get_or_create hatası: {e}")
            # Hata durumunda boş istatistik döndür, akışı bozmamak için
            return {
                "user_id": user_id,
                "total_challenges": 0,
                "completed_challenges": 0,
                "total_points": 0,
            }

    def _update_fields(self, user_id: str, fields: Dict[str, Any]) -> None:
        """Belirtilen alanları user_id'ye göre günceller."""
        if not fields:
            return
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [user_id]

        try:
            with self.db_client.get_connection() as conn:
                cursor = conn.cursor()
                sql = f"""
                    UPDATE {self.table_name}
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """
                cursor.execute(sql, values)
                conn.commit()
        except Exception as e:
            logger.error(f"[X] user_challenge_stats._update_fields hatası: {e}")

    def add_points(self, user_id: str, points: int):
        """Kullanıcıya puan ekler."""
        stats = self.get_or_create(user_id)
        new_total = stats.get("total_points", 0) + points
        self._update_fields(user_id, {"total_points": new_total})

    def increment_total(self, user_id: str):
        """Toplam challenge sayısını artırır (katıldığı challenge'lar)."""
        stats = self.get_or_create(user_id)
        new_count = stats.get("total_challenges", 0) + 1
        self._update_fields(user_id, {"total_challenges": new_count})

    def increment_completed(self, user_id: str):
        """Tamamlanan challenge sayısını artırır."""
        stats = self.get_or_create(user_id)
        new_count = stats.get("completed_challenges", 0) + 1
        self._update_fields(user_id, {"completed_challenges": new_count})
