import threading


class RegisterMap:
    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[str, dict[int, float]] = {}

    def write(self, node_id: str, register: int, value: float):
        with self._lock:
            if node_id not in self._store:
                self._store[node_id] = {}
            self._store[node_id][register] = value

    def write_batch(self, node_id: str, registers: dict[int, float]):
        with self._lock:
            if node_id not in self._store:
                self._store[node_id] = {}
            self._store[node_id].update(registers)

    def read(self, node_id: str, register: int) -> float:
        with self._lock:
            return self._store.get(node_id, {}).get(register, 0.0)

    def read_all(self, node_id: str) -> dict[int, float]:
        with self._lock:
            return dict(self._store.get(node_id, {}))

    def get_node_ids(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())

    def snapshot(self) -> dict[str, dict[int, float]]:
        with self._lock:
            return {nid: dict(regs) for nid, regs in self._store.items()}
