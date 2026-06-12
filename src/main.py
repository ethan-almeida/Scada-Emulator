import threading
import signal
import time
from pathlib import Path

from config import load_config
from storage.database import Database
from emulation.register_map import RegisterMap
from emulation.wind_node import WindNode
from emulation.solar_node import SolarNode

BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    cfg = load_config(BASE_DIR / "config.yaml")

    db = Database(cfg.database.path, cfg.database.wal_mode)
    db.init_schema(BASE_DIR / "schema.sql")
    db.close()

    print(f"Database initialized at {cfg.database.path}")

    reg_map = RegisterMap()
    running = threading.Event()
    running.set()

    threads = []

    for i in range(1, cfg.wind_nodes.count + 1):
        node_id = f"wind_{i:02d}"
        regs = {k: v + (i - 1) * 100 for k, v in cfg.wind_nodes.registers.__dict__.items()}
        node = WindNode(node_id, cfg.wind_nodes.rated_capacity_kw, regs, cfg.emulation_interval)
        t = threading.Thread(target=node.run, args=(reg_map, running), daemon=True)
        threads.append(t)
        t.start()
        print(f"  Started {node_id}")

    for i in range(1, cfg.solar_nodes.count + 1):
        node_id = f"solar_{i:02d}"
        regs = {k: v + (i - 1) * 100 for k, v in cfg.solar_nodes.registers.__dict__.items()}
        node = SolarNode(node_id, cfg.solar_nodes.rated_capacity_kw, regs, cfg.emulation_interval)
        t = threading.Thread(target=node.run, args=(reg_map, running), daemon=True)
        threads.append(t)
        t.start()
        print(f"  Started {node_id}")

    print(f"\nAll {len(threads)} nodes running. Press Ctrl+C to stop.\n")

    def shutdown(sig, frame):
        print("\nShutting down...")
        running.clear()
        for t in threads:
            t.join(timeout=3)
        print("All nodes stopped.")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
