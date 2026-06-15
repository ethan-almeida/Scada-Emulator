import json
import pandas as pd
import numpy as np
from storage.database import Database

class AnomalyDetector:
    def __init__(self, db: Database, rolling_window: int = 20, power_ratio_threshold: float = 0.6):
        self.db = db
        self.rolling_window = rolling_window
        self.power_ratio_threshold = power_ratio_threshold

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

    def _detect_wind_anomalies(self, node_df: pd.DataFrame, rated_kw: float) -> pd.DataFrame:
        node_df = node_df.copy()
        node_df["expected_power"] = 0.5 * 1.225 * (80**2 / 4 * np.pi) * 0.45 * node_df[0] ** 3 / 1000.0
        node_df["expected_power"] = node_df["expected_power"].clip(upper=rated_kw)
        node_df["power_ratio"] = np.where(
            node_df["expected_power"] > 0, node_df[2] / node_df["expected_power"], 1.0
        )
        node_df["rolling_ratio"] = node_df["power_ratio"].rolling(
            window=self.rolling_window, min_periods=1
        ).mean()
        node_df["rolling_rpm_z"] = node_df[1].rolling(
            window=self.rolling_window, min_periods=3
        ).apply(lambda x: (x.iloc[-1] - x.mean()) / x.std() if x.std() > 0 else 0, raw=False)
        node_df["flags"] = ""
        low_ratio = node_df["rolling_ratio"] < self.power_ratio_threshold
        node_df.loc[low_ratio, "flags"] = "LOW_POWER_RATIO;"
        low_rpm = (node_df[0] > 6.0) & (node_df[1] < 3.0) & (node_df[2] > 0)
        node_df.loc[low_rpm, "flags"] += "LOW_RPM_UNDER_LOAD;"
        high_temp = node_df[3] > 50.0
        node_df.loc[high_temp, "flags"] += "HIGH_NACELLE_TEMP;"
        voltage_swing = (node_df[4] < 470.0) | (node_df[4] > 490.0)
        node_df.loc[voltage_swing, "flags"] += "VOLTAGE_SWING;"
        return node_df

    def _detect_solar_anomalies(self, node_df: pd.DataFrame, rated_kw: float) -> pd.DataFrame:
        node_df = node_df.copy()
        node_df["expected_power"] = node_df[10] * 0.18 * (rated_kw / (0.18 * 1.0)) / 1000.0
        node_df["power_ratio"] = np.where(
            node_df["expected_power"] > 0, node_df[12] / node_df["expected_power"], 1.0
        )
        node_df["rolling_ratio"] = node_df["power_ratio"].rolling(
            window=self.rolling_window, min_periods=1
        ).mean()
        node_df["flags"] = ""
        low_ratio = node_df["rolling_ratio"] < self.power_ratio_threshold
        node_df.loc[low_ratio, "flags"] = "LOW_POWER_RATIO;"
        high_cell_temp = node_df[11] > 65.0
        node_df.loc[high_cell_temp, "flags"] += "HIGH_CELL_TEMP;"
        low_irradiance_high_temp = (node_df[10] < 200.0) & (node_df[11] > 50.0)
        node_df.loc[low_irradiance_high_temp, "flags"] += "THERMAL_MISMATCH;"
        zero_current = (node_df[10] > 100.0) & (node_df[14] < 0.1)
        node_df.loc[zero_current, "flags"] += "STRING_FAILURE;"
        return node_df

    def detect(self) -> int:
        df = self._load_clean()
        if df.empty:
            return 0

        pivoted = df.pivot_table(
            index=["timestamp", "node_id"], columns="register", values="value", aggfunc="first"
        ).reset_index()
        pivoted.columns.name = None

        all_flags = []
        for nid in pivoted["node_id"].unique():
            ndf = pivoted[pivoted["node_id"] == nid].copy()
            is_wind = nid.startswith("wind")
            rated = 2000.0 if is_wind else 1500.0

            if is_wind:
                detected = self._detect_wind_anomalies(ndf, rated)
            else:
                detected = self._detect_solar_anomalies(ndf, rated)

            for _, row in detected.iterrows():
                flags = row["flags"].rstrip(";")
                if flags:
                    all_flags.append({
                        "node_id": nid,
                        "timestamp": row["timestamp"],
                        "flags": flags,
                    })

        if all_flags:
            conn = self.db.get_thread_conn()
            for entry in all_flags:
                existing_row = conn.execute(
                    "SELECT anomaly_flags FROM metric_snaps WHERE node_id = ? AND timestamp = ?",
                    (entry["node_id"], str(entry["timestamp"])),
                ).fetchone()
                if existing_row:
                    old_flags = json.loads(existing_row[0]) if existing_row[0] else []
                    new_flag = entry["flags"]
                    if new_flag not in old_flags:
                        old_flags.append(new_flag)
                    conn.execute(
                        "UPDATE metric_snaps SET anomaly_flags = ? WHERE node_id = ? AND timestamp = ?",
                        (json.dumps(old_flags), entry["node_id"], str(entry["timestamp"])),
                    )
            conn.commit()

        return len(all_flags)