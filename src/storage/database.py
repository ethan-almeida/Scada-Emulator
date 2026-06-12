import sqlite3
from pathlib import Path

class Database:
    def __init__(self, db_path: str, wal_mode: bool=True):
        self.db_path = db_path
        self.wal_mode = wal_mode
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        if self.wal_mode:
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        return self._conn

    def init_schema(self, schema_path: str = "schema.sql"):
        conn = self._conn or self.connect()
        with open(schema_path, "r") as f:
            conn.executescript(f.read())
        conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

