import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
from storage.database import Database

class PdfReporter:
    def __init__(self, db: Database, output_dir: str):
        self.db = db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        conn = self.db.get_thread_conn()
        clean = pd.read_sql_query("SELECT * FROM clean_telemetry", conn)
        if not clean.empty:
            clean["timestamp"] = pd.to_datetime(clean["timestamp"])
        kpis = pd.read_sql_query("SELECT * FROM metric_snaps", conn)
        if not kpis.empty:
            kpis["timestamp"] = pd.to_datetime(kpis["timestamp"])
        anomalies = pd.read_sql_query(
            "SELECT * FROM metric_snaps WHERE anomaly_flags != '[]'", conn
        )
        return clean, kpis, anomalies

    def _title_page(self, pdf, report_time):
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis("off")
        ax.text(0.5, 0.6, "SCADA Telemetry Report", fontsize=28, fontweight="bold",
                ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.45, f"Generated: {report_time}", fontsize=14,
                ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.35, "Wind & Solar Asset Monitoring", fontsize=12, color="gray",
                ha="center", va="center", transform=ax.transAxes)
        pdf.savefig(fig)
        plt.close(fig)

    def _node_timeseries(self, pdf, clean_df, node_id, is_wind):
        node_data = clean_df[clean_df["node_id"] == node_id].copy()
        if node_data.empty:
            return

        if is_wind:
            reg_map = {0: "Wind Speed (m/s)", 1: "Rotor RPM", 2: "Power Output (kW)",
                       3: "Nacelle Temp (°C)", 4: "Grid Voltage (V)"}
        else:
            reg_map = {10: "Irradiance (W/m²)", 11: "Cell Temp (°C)", 12: "Power Output (kW)",
                       13: "DC Voltage (V)", 14: "String Current (A)"}

        fig, axes = plt.subplots(len(reg_map), 1, figsize=(12, 3 * len(reg_map)), sharex=True)
        fig.suptitle(f"{node_id} — Telemetry Time Series", fontsize=14, fontweight="bold")

        for ax, (reg, label) in zip(axes, reg_map.items()):
            subset = node_data[node_data["register"] == reg].sort_values("timestamp")
            ax.plot(subset["timestamp"], subset["value"], linewidth=0.8, color="steelblue")
            ax.set_ylabel(label, fontsize=9)
            ax.grid(True, alpha=0.3)

        axes[-1].set_xlabel("Time")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    def _kpi_summary(self, pdf, kpis_df):
        if kpis_df.empty:
            return

        latest = kpis_df.sort_values("timestamp").groupby("node_id").last().reset_index()

        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        fig.suptitle("KPI Summary — Latest Snapshot", fontsize=14, fontweight="bold")

        for ax, metric, color in zip(
            axes,
            ["performance_ratio", "capacity_factor", "availability"],
            ["steelblue", "darkorange", "green"],
        ):
            ax.bar(latest["node_id"], latest[metric], color=color, alpha=0.8)
            ax.set_title(metric.replace("_", " ").title(), fontsize=11)
            ax.set_ylim(0, 1.5)
            ax.tick_params(axis="x", rotation=45)
            ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    def _anomaly_summary(self, pdf, anomalies_df):
        if anomalies_df.empty:
            return

        flag_counts = {}
        for _, row in anomalies_df.iterrows():
            import json
            flags = json.loads(row["anomaly_flags"])
            for f in flags:
                flag_counts[f] = flag_counts.get(f, 0) + 1

        if not flag_counts:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(list(flag_counts.keys()), list(flag_counts.values()), color="crimson", alpha=0.8)
        ax.set_xlabel("Occurrences")
        ax.set_title("Anomaly Flags Summary", fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="x")
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    def generate(self) -> str:
        clean, kpis, anomalies = self._load_data()
        if clean.empty:
            return ""

        report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = self.output_dir / f"scada_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        with PdfPages(str(filename)) as pdf:
            self._title_page(pdf, report_time)

            node_ids = clean["node_id"].unique()
            for nid in sorted(node_ids):
                self._node_timeseries(pdf, clean, nid, nid.startswith("wind"))

            self._kpi_summary(pdf, kpis)
            self._anomaly_summary(pdf, anomalies)

        return str(filename)