import pandas as pd
import numpy as np
from storage.database import Database

class DataScrubber:
    def __init__(self, db: Database, zscore_threshold: float = 3.0, max_gap: int = 5):
        self.db = db
        self.zscore_threshold = zscore_threshold
        self.max_gap = max_gap

    def _load_raw(self) -> pd.DataFrame:
        conn = self.db.get_thread_conn()
        df = pd.read_sql_query(
            "SELECT id, timestamp, node_id, register, value, quality FROM raw_telemetry ORDER BY timestamp", 
            conn,
        )

        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def _flag_outliers(self, group: pd.Series) -> pd.Series:
        if len(group) < 3:
            return pd.Series(False, index=group.index)
        zscores = np.abs((group - group.mean()) / group.std())
        return zscores > self.zscore_threshold

    def _interpolate_gaps(self, group: pd.Series) -> pd.Series:
        mask = group.isna()
        if not mask.any():
            return group
        gaps = mask.groupby((~mask).cumsum()).transform("sum")
        group = group.copy()
        group[mask & (gaps <= self.max_gap)] = np.nan
        return group.interpolate(limit=self.max_gap)

    def scrub(self) -> int:
        df = self._load_raw()
        if df.empty:
            return 0
        df["scrubbed"] = 0

        mask_neg = (df["register"].isin([2, 12])) & (df["value"] < 0)
        df.loc[mask_neg, "value"] = 0
        df.loc[mask_neg, "scrubbed"] = 1

        outlier_mask = df.groupby(["node_id", "register"])["value"].transform(self._flag_outliers)
        df.loc[outlier_mask, "value"] = np.nan
        df.loc[outlier_mask, "scrubbed"] = 1

        df["value"] = df.groupby(["node_id", "register"])["value"].transform(self._interpolate_gaps)

        df = df.dropna(subset=["value"])

        conn = self.db.get_thread_conn()
        rows = df[["timestamp", "node_id", "register", "value", "quality", "scrubbed"]].copy()
        rows["timestamp"] = rows["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        rows.to_sql("clean_telemetry", conn, if_exists="append", index=False)
        conn.commit()

        return len(rows)