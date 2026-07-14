from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ChurnConfig:
    online_seconds: int = 10
    offline_seconds: int = 5
    cycles: int = 3
    jitter_seconds: int = 0


class ChurnController:
    """Repeatedly takes one peer offline and brings it back online."""

    def __init__(self, node):
        self.node = node
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._lock = threading.RLock()

        self.on_state: Callable[[dict], None] | None = None
        self.on_log: Callable[[str], None] | None = None
        self.on_finished: Callable[[dict], None] | None = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def set_callbacks(self, *, state=None, log=None, finished=None):
        self.on_state = state
        self.on_log = log
        self.on_finished = finished

    def _emit_state(self, online: bool, cycle: int, total: int, phase: str):
        if self.on_state:
            self.on_state({
                "online": online,
                "cycle": cycle,
                "total_cycles": total,
                "phase": phase,
            })

    def _emit_log(self, text: str):
        if self.on_log:
            self.on_log(text)

    def start(self, config: ChurnConfig) -> str | None:
        with self._lock:
            if self._running:
                return "Mô phỏng churn đang chạy."
            if min(config.online_seconds, config.offline_seconds, config.cycles) < 1:
                return "Thời gian và số vòng phải từ 1."
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(config,),
                daemon=True,
                name=f"churn-{self.node.username}",
            )
            self._thread.start()
        return None

    def stop(self, reconnect: bool = True):
        self._stop_event.set()
        if reconnect and not self.node.is_online:
            self.node.go_online()

    def _duration(self, base: int, jitter: int) -> int:
        if jitter <= 0:
            return base
        return max(1, base + random.randint(-jitter, jitter))

    def _run(self, config: ChurnConfig):
        completed = 0
        stopped = False
        error = ""
        try:
            self._emit_log(
                f"Bắt đầu {config.cycles} vòng: online {config.online_seconds}s, "
                f"offline {config.offline_seconds}s."
            )
            for cycle in range(1, config.cycles + 1):
                if self._stop_event.is_set():
                    stopped = True
                    break

                online_duration = self._duration(
                    config.online_seconds, config.jitter_seconds
                )
                self._emit_state(True, cycle, config.cycles, "online_wait")
                self._emit_log(
                    f"Vòng {cycle}/{config.cycles}: online {online_duration} giây."
                )
                if self._stop_event.wait(online_duration):
                    stopped = True
                    break

                self._emit_log(
                    f"Vòng {cycle}/{config.cycles}: unregister và đóng TCP server."
                )
                if not self.node.go_offline():
                    error = "Không thể chuyển peer sang offline."
                    break
                self._emit_state(False, cycle, config.cycles, "offline_wait")

                offline_duration = self._duration(
                    config.offline_seconds, config.jitter_seconds
                )
                self._emit_log(
                    f"Vòng {cycle}/{config.cycles}: offline {offline_duration} giây."
                )
                if self._stop_event.wait(offline_duration):
                    stopped = True
                    break

                self._emit_log(
                    f"Vòng {cycle}/{config.cycles}: mở TCP server và register lại."
                )
                if not self.node.go_online():
                    error = "Không thể đăng ký lại với bootstrap."
                    break

                completed = cycle
                self._emit_state(True, cycle, config.cycles, "rejoined")
                self._emit_log(
                    f"Vòng {cycle}/{config.cycles}: online lại, đã kiểm tra tin chờ."
                )
        except Exception as exc:
            error = str(exc)
        finally:
            if not self.node.is_online:
                self._emit_log("Khôi phục peer về online trước khi kết thúc…")
                self.node.go_online()

            with self._lock:
                self._running = False

            result = {
                "stopped": stopped or self._stop_event.is_set(),
                "completed_cycles": completed,
                "total_cycles": config.cycles,
                "error": error,
                "online": self.node.is_online,
            }
            if error:
                self._emit_log(f"Lỗi: {error}")
            elif result["stopped"]:
                self._emit_log("Đã dừng mô phỏng churn.")
            else:
                self._emit_log(
                    f"Hoàn thành {completed}/{config.cycles} vòng churn."
                )
            if self.on_finished:
                self.on_finished(result)
