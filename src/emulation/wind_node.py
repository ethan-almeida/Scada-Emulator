import threading
import math
import random


class WindNode:
    def __init__(self, node_id: str, rated_capacity_kw: int, registers: dict, interval: float):
        self.node_id = node_id
        self.rated_capacity_kw = rated_capacity_kw
        self.registers = registers
        self.interval = interval

        self.wind_speed = random.uniform(5.0, 10.0)
        self.nacelle_temp = 25.0

        self._rho = 1.225
        self._rotor_diameter = 80.0
        self._cp = 0.45
        self._cut_in = 3.0
        self._rated_speed = 12.0
        self._cut_out = 25.0
        self._max_rpm = 18.0
        self._ambient_temp = 20.0

    def _update_wind_speed(self):
        gust = random.gauss(0, 1.5)
        self.wind_speed += gust
        self.wind_speed = max(0.0, min(25.0, self.wind_speed))
        mean_revert = 0.05 * (8.0 - self.wind_speed)
        self.wind_speed += mean_revert
        self.wind_speed = max(0.0, min(25.0, self.wind_speed))

    def _calc_rpm(self) -> float:
        if self.wind_speed < self._cut_in or self.wind_speed > self._cut_out:
            return 0.0
        if self.wind_speed >= self._rated_speed:
            return self._max_rpm
        ratio = (self.wind_speed - self._cut_in) / (self._rated_speed - self._cut_in)
        return ratio * self._max_rpm

    def _calc_power(self) -> float:
        if self.wind_speed < self._cut_in or self.wind_speed > self._cut_out:
            return 0.0
        area = math.pi * (self._rotor_diameter / 2) ** 2
        power_w = 0.5 * self._rho * area * self._cp * self.wind_speed ** 3
        power_kw = power_w / 1000.0
        return min(power_kw, self.rated_capacity_kw)

    def _update_nacelle_temp(self, power_fraction: float):
        generator_heat = power_fraction * 15.0
        self.nacelle_temp = self._ambient_temp + generator_heat + random.gauss(0, 0.5)

    def generate(self) -> dict[int, float]:
        self._update_wind_speed()
        rpm = self._calc_rpm()
        power = self._calc_power()
        power_fraction = power / self.rated_capacity_kw
        self._update_nacelle_temp(power_fraction)
        grid_voltage = 480.0 + random.gauss(0, 2.0)

        return {
            self.registers["wind_speed"]: round(self.wind_speed, 2),
            self.registers["rotor_rpm"]: round(rpm, 1),
            self.registers["power_output"]: round(power, 2),
            self.registers["nacelle_temp"]: round(self.nacelle_temp, 1),
            self.registers["grid_voltage"]: round(grid_voltage, 1),
        }

    def run(self, register_map, running: threading.Event):
        while not running.is_set():
            regs = self.generate()
            register_map.write_batch(self.node_id, regs)
            running.wait(self.interval)
