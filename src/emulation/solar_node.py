import threading
import math
import random
from datetime import datetime


class SolarNode:
    def __init__(self, node_id: str, rated_capacity_kw: int, registers: dict, interval: float):
        self.node_id = node_id
        self.rated_capacity_kw = rated_capacity_kw
        self.registers = registers
        self.interval = interval

        self._ambient_temp = 25.0
        self._efficiency = 0.18
        self._area_m2 = rated_capacity_kw / (0.18 * 1.0)
        self._temp_coeff = -0.004
        self._nominal_voltage = 600.0

    def _solar_irradiance(self) -> float:
        hour = datetime.now().hour + datetime.now().minute / 60.0
        peak = 12.0
        width = 6.0
        base = max(0.0, math.exp(-((hour - peak) ** 2) / (2 * width ** 2)))
        cloud_dip = random.uniform(0.7, 1.0) if random.random() < 0.15 else 1.0
        return base * 1000.0 * cloud_dip

    def _calc_cell_temp(self, irradiance: float) -> float:
        return self._ambient_temp + irradiance * 0.03 + random.gauss(0, 0.3)

    def _calc_power(self, irradiance: float, cell_temp: float) -> float:
        temp_loss = 1.0 + self._temp_coeff * (cell_temp - 25.0)
        power = irradiance * self._efficiency * self._area_m2 * temp_loss / 1000.0
        return max(0.0, min(power, self.rated_capacity_kw))

    def _calc_voltage(self, cell_temp: float) -> float:
        return self._nominal_voltage * (1.0 + self._temp_coeff * (cell_temp - 25.0))

    def generate(self) -> dict[int, float]:
        irradiance = self._solar_irradiance()
        cell_temp = self._calc_cell_temp(irradiance)
        power = self._calc_power(irradiance, cell_temp)
        voltage = self._calc_voltage(cell_temp)
        current = (power * 1000.0 / voltage) if voltage > 0 else 0.0

        return {
            self.registers["irradiance"]: round(irradiance, 2),
            self.registers["cell_temp"]: round(cell_temp, 1),
            self.registers["power_output"]: round(power, 2),
            self.registers["dc_voltage"]: round(voltage, 1),
            self.registers["string_current"]: round(current, 2),
        }

    def run(self, register_map, running: threading.Event):
        while not running.is_set():
            regs = self.generate()
            register_map.write_batch(self.node_id, regs)
            running.wait(self.interval)
