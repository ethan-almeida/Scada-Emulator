import threading
from datetime import datetime, timezone
from storage.database import Database

class TelemetryLogger:
    def __init__(self, register_map, db: Database):
        self.register_map = register_map
        self.db = db

    def _log_cycle(self):
        now = datetime.now(timezone.utc).isoformat()
        snap = self.register_map.snapshot()
        rows = []
        for node_id, regs in snap.items():
            for addr, val in regs.items():
                rows.append((now, node_id, addr, val, 0))
        if rows:
            conn = self.db.get_thread_conn()
            conn.executemany(
                "INSERT INTO raw_telemetry (timestamp, node_id, register, value, quality) VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
    
    def run(self, stop: threading.Event, interval: float = 5.0):
        while not stop.is_set():
            self._log_cycle()
            stop.wait(interval)
    
    def start(self, stop: threading.Event, interval: float = 5.0):
        t = threading.Thread(target=self.run, args=(stop, interval), daemon=True)
        t.start()