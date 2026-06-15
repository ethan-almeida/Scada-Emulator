import threading
import signal
import time
from pathlib import Path

from config import load_config
from storage.database import Database
from emulation.register_map import RegisterMap
from emulation.wind_node import WindNode
from emulation.solar_node import SolarNode
from modbus.server import ModbusServer
from storage.logger import TelemetryLogger
from analytics.scrubber import DataScrubber
from analytics.kpi import KpiCalculator
from analytics.anomaly import AnomalyDetector
from reports.pdf_export import PdfReporter

BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    cfg = load_config(BASE_DIR / "config.yaml")

    db = Database(cfg.database.path, cfg.database.wal_mode)
    db.init_schema(BASE_DIR / "schema.sql")

    print(f"Database initialized at {cfg.database.path}")

    reg_map = RegisterMap()
    stop = threading.Event()

    threads = []

    for i in range(1, cfg.wind_nodes.count + 1):
        node_id = f"wind_{i:02d}"
        regs = {k: v + (i - 1) * 100 for k, v in cfg.wind_nodes.registers.__dict__.items()}
        node = WindNode(node_id, cfg.wind_nodes.rated_capacity_kw, regs, cfg.emulation_interval)
        t = threading.Thread(target=node.run, args=(reg_map, stop), daemon=True)
        threads.append(t)
        t.start()
        print(f"  Started {node_id}")

    for i in range(1, cfg.solar_nodes.count + 1):
        node_id = f"solar_{i:02d}"
        regs = {k: v + (i - 1) * 100 for k, v in cfg.solar_nodes.registers.__dict__.items()}
        node = SolarNode(node_id, cfg.solar_nodes.rated_capacity_kw, regs, cfg.emulation_interval)
        t = threading.Thread(target=node.run, args=(reg_map, stop), daemon=True)
        threads.append(t)
        t.start()
        print(f"  Started {node_id}")

    modbus = ModbusServer(reg_map, cfg.modbus.host, cfg.modbus.port, cfg.modbus.unit_id)
    modbus.start(stop)
    print(f"  Modbus TCP server on {cfg.modbus.host}:{cfg.modbus.port}")

    logger = TelemetryLogger(reg_map, db)
    logger.start(stop, cfg.database.batch_flush_interval)
    print(f"  Telemetry logger (every {cfg.database.batch_flush_interval}s)")
    scrubber = DataScrubber(db, cfg.scrubbing.zscore_threshold, cfg.scrubbing.interpolation_max_gap)
    kpi_calc = KpiCalculator(db, cfg.kpi.window_minutes)
    anomaly = AnomalyDetector(db, cfg.anomaly.rolling_window, cfg.anomaly.power_ratio_threshold)
    reporter = PdfReporter(db, cfg.reports.output_dir)

    def periodic_analytics():
        while not stop.is_set():
            stop.wait(30)
            n = scrubber.scrub()
            if n:
                print(f"  Scrubbed {n} rows")
            m = kpi_calc.calculate()
            if m:
                print(f"  Computed {m} KPI snapshots")
            a = anomaly.detect()
            if a:
                print(f"  Flagged {a} anomaly events")
            f = reporter.generate()
            if f:
                print(f"  Report exported: {f}")

    threading.Thread(target=periodic_analytics, daemon=True).start()
    print("  Analytics engine running (every 30s)")
    print(f"\nAll {len(threads)} nodes + Modbus server + logger running. Press Ctrl+C to stop.\n")

    def shutdown(sig, frame):
        print("\nShutting down...")
        stop.set()
        for t in threads:
            t.join(timeout=3)
        db.close()
        print("All nodes stopped.")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()