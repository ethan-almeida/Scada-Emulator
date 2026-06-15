import asyncio
import threading
import time
from pymodbus.simulator import SimData, SimDevice
from pymodbus.simulator.simdata import DataType
from pymodbus.server import ModbusTcpServer


class ModbusServer:
    def __init__(self, register_map, host: str, port: int, unit_id: int):
        self.register_map = register_map
        self.host = host
        self.port = port
        self.unit_id = unit_id

        holding = SimData(address=1, count=500, values=0, datatype=DataType.REGISTERS)
        self.device = SimDevice(unit_id, simdata=holding)

        self._loop = None
        self._context = None

    async def _serve(self):
        server = ModbusTcpServer(self.device, address=(self.host, self.port))
        self._context = server.context
        await server.serve_forever()

    def _run_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    def _sync_loop(self, running: threading.Event, interval: float):
        while not running.is_set():
            snap = self.register_map.snapshot()
            for node_id, regs in snap.items():
                for addr, val in regs.items():
                    modbus_addr = addr + 1
                    future = asyncio.run_coroutine_threadsafe(
                        self._context.async_setValues(
                            self.unit_id, 3, modbus_addr, [int(val * 10)]
                        ),
                        self._loop,
                    )
                    future.result(timeout=2)
            running.wait(interval)

    def start(self, running: threading.Event, sync_interval: float = 1.0):
        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        time.sleep(2)

        s = threading.Thread(
            target=self._sync_loop, args=(running, sync_interval), daemon=True
        )
        s.start()