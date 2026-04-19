import mysql.connector
from mysql.connector import pooling
from config import get_settings

settings = get_settings()
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="mathurapharmeasy",
            pool_size=15,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4",
            autocommit=False,
        )
    return _pool

def get_conn():
    return get_pool().get_connection()

class DB:
    """Context manager — auto commit/rollback, auto close."""
    def __enter__(self):
        self.conn   = get_conn()
        self.cursor = self.conn.cursor(dictionary=True)
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def fetchall(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

    def fetchone(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchone()

    def execute(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor

    def insert(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.lastrowid
