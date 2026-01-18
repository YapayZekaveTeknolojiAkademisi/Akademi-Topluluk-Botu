"""
Database transaction yönetimi için context manager.
"""

from contextlib import contextmanager
from typing import Generator
from src.clients.database_client import DatabaseClient
from src.core.logger import logger
from src.core.exceptions import DatabaseError


@contextmanager
def transaction(db_client: DatabaseClient) -> Generator:
    """
    Database transaction context manager.
    
    Usage:
        with transaction(db_client) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            # commit otomatik yapılır
    """
    conn = None
    try:
        conn = db_client.get_connection()
        yield conn
        conn.commit()
        logger.debug("[+] Transaction başarıyla commit edildi")
    except Exception as e:
        if conn:
            conn.rollback()
            logger.error(f"[X] Transaction rollback edildi: {e}")
        raise DatabaseError(f"Transaction hatası: {e}")
    finally:
        if conn:
            conn.close()
