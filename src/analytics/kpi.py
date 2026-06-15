import json
import pandas as pd
import numpy as np
from storage.database import Database


class KpiCalculator:
    def __init__(self, db: Database, window_minutes: int = 60):
        self.db = db
        self.window_minutes = window_minutes

    def _load_clean(self) -> pd.DataFrame:
        conn = self.db.get_thread_conn()
        df = pd.read_sql_query(
            "SELECT timestamp, node_id, register, value FROM clean_telemetry ORDER BY timestamp",
            conn,
        )
        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def _pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        pivoted = df.pivot_table(
            index=["timestamp", "node_id"],
            columns="register",
            values="value",
            aggfunc="first",
        ).reset_index()
        pivoted.columns.name = None
        return pivoted

    def _calc_wind_kpis(self, node_df: pd.DataFrame, rated_kw: float) -> pd.DataFrame:
        node_df = node_df.sort_values("timestamp")
        node_df["power_fraction"] = node_df[2] / rated_kw
        node_df["availability"] = (node_df[2] > 0).astype(float)

        node_df["capacity_factor"] = node_df["power_fraction"]

        expected = 0.5 * 1.225 * (80 ** 2 / 4 * np.pi) * 0.45 * node_df[0] ** 3 / 1000.0
        expected = expected.clip(upper=rated_kw)
        node_df["performance_ratio"] = np.where(
            expected > 0, node_df[2] / expected, 0.0
        ).clip(max=1.5)

        return node_df

    def _calc_solar_kpis(self, node_df: pd.DataFrame, rated_kw: float) -> pd.DataFrame:
        node_df = node_df.sort_values("timestamp")
        node_df["power_fraction"] = node_df[12] / rated_kw
        node_df["availability"] = (node_df[12] > 0).astype(float)

        node_df["capacity_factor"] = node_df["power_fraction"]

        expected = node_df[10] * 0.18 * (rated_kw / (0.18 * 1.0)) / 1000.0
        node_df["performance_ratio"] = np.where(
            expected > 0, node_df[12] / expected, 0.0
        ).clip(max=1.5)

        return node_df

    def calculate(self) -> int:
        df = self._load_clean()
        if df.empty:
            return 0

        pivoted = self._pivot(df)
        node_ids = pivoted["node_id"].unique()

        results = []
        for nid in node_ids:
            ndf = pivoted[pivoted["node_id"] == nid].copy()
            is_wind = nid.startswith("wind")
            rated = 2000.0 if is_wind else 1500.0

            if is_wind:
                kpis = self._calc_wind_kpis(ndf, rated)
            else:
                kpis = self._calc_solar_kpis(ndf, rated)

            for _, row in kpis.iterrows():
                results.append({
                    "timestamp": row["timestamp"],
                    "node_id": nid,
                    "window_minutes": self.window_minutes,
                    "performance_ratio": round(row.get("performance_ratio", 0), 4),
                    "capacity_factor": round(row.get("capacity_factor", 0), 4),
                    "availability": round(row.get("availability", 0), 4),
                    "anomaly_flags": json.dumps([]),
                })

        if results:
            conn = self.db.get_thread_conn()
            pd.DataFrame(results).to_sql("metric_snaps", conn, if_exists="append", index=False)
            conn.commit()

        return len(results)