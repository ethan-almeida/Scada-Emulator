from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class ModbusConfig:
    host: str = "0.0.0.0"
    port: int = 5020
    unit_id: int = 1

@dataclass
class NodeRegisters:
    wind_speed: int = 0
    rotor_rpm: int = 1
    power_output: int = 2
    nacelle_temp: int = 3
    grid_voltage: int = 4

@dataclass
class SolarRegisters:
    irradiance: int = 10
    cell_temp: int = 11
    power_output: int = 12
    dc_voltage: int = 13
    string_current: int = 14

@dataclass
class NodeConfig:
    count: int = 3
    rated_capacity_kw: int = 2000
    registers: NodeRegisters | SolarRegisters = field(default_factory=NodeRegisters)

@dataclass
class DatabaseConfig:
    path: str = "output/scada.db"
    wal_mode: bool = True
    batch_flush_interval: int = 5


@dataclass
class ScrubConfig:
    zscore_threshold: float = 3.0
    interpolation_max_gap: int = 5


@dataclass
class KpiConfig:
    window_minutes: int = 60


@dataclass
class AnomalyConfig:
    rolling_window: int = 20
    power_ratio_threshold: float = 0.6


@dataclass
class ReportConfig:
    output_dir: str = "output/reports"
    schedule: str = "daily"


@dataclass
class AppConfig:
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    wind_nodes: NodeConfig = field(default_factory=NodeConfig)
    solar_nodes: NodeConfig = field(default_factory=NodeConfig)
    emulation_interval: int = 2
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scrubbing: ScrubConfig = field(default_factory=ScrubConfig)
    kpi: KpiConfig = field(default_factory=KpiConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    reports: ReportConfig = field(default_factory=ReportConfig)


def load_config(path: str = "config.yaml") -> AppConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    cfg = AppConfig()
    cfg.modbus = ModbusConfig(**raw.get("modbus", {}))

    emu = raw.get("emulation", {})
    cfg.emulation_interval = emu.get("interval_seconds", 2)

    wind = emu.get("wind_nodes", {})
    cfg.wind_nodes = NodeConfig(
        count=wind.get("count", 3),
        rated_capacity_kw=wind.get("rated_capacity_kw", 2000),
        registers=NodeRegisters(**wind.get("registers", {})),
    )

    solar = emu.get("solar_nodes", {})
    cfg.solar_nodes = NodeConfig(
        count=solar.get("count", 3),
        rated_capacity_kw=solar.get("rated_capacity_kw", 1500),
        registers=SolarRegisters(**solar.get("registers", {})),
    )

    cfg.database = DatabaseConfig(**raw.get("database", {}))

    analytics = raw.get("analytics", {})
    cfg.scrubbing = ScrubConfig(**analytics.get("scrubbing", {}))
    cfg.kpi = KpiConfig(**analytics.get("kpi", {}))
    cfg.anomaly = AnomalyConfig(**analytics.get("anomaly", {}))

    cfg.reports = ReportConfig(**raw.get("reports", {}))

    return cfg