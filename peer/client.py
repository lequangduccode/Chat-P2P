"""PeerClient – gửi dữ liệu, giao tiếp bootstrap và lưu hàng đợi offline bền vững."""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

from common.protocol import MsgType, encode_msg, make_msg, recv_msg
from config import CONNECT_TIMEOUT, RECV_TIMEOUT

log = logging.getLogger(__name__)


class PeerClient:
    """TCP client with persistent store-and-forward.

    Pending queues are keyed by normalized username instead of peer_id. A peer_id
    is regenerated after every restart, while username remains stable in this
    project. This prevents messages being stranded under an obsolete peer_id.
    """

    def __init__(self, bootstrap_host: str, bootstrap_port: int, storage_owner: str = "peer"):
        self._bs_host = bootstrap_host
        self._bs_port = bootstrap_port
        self._pending: dict[str, list[dict]] = {}
        self._pending_lock = threading.RLock()

        safe_owner = self._safe_name(storage_owner)
        data_root = Path(os.environ.get("P2P_DATA_DIR", ".p2p_data"))
        self._storage_dir = data_root / safe_owner
        self._pending_file = self._storage_dir / "pending_messages.json"
        self._load_pending()

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())
        return cleaned or "peer"

    @staticmethod
    def _queue_key(username: str) -> str:
        return username.strip().casefold()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_pending(self) -> None:
        try:
            if not self._pending_file.exists():
                return
            raw = json.loads(self._pending_file.read_text(encoding="utf-8"))
            queues = raw.get("queues", raw) if isinstance(raw, dict) else {}
            if not isinstance(queues, dict):
                raise ValueError("pending queue must be a JSON object")
            with self._pending_lock:
                self._pending = {
                    self._queue_key(str(name)): [m for m in messages if isinstance(m, dict)]
                    for name, messages in queues.items()
                    if isinstance(messages, list)
                }
                self._pending = {k: v for k, v in self._pending.items() if v}
        except Exception as exc:
            log.warning("Không đọc được hàng đợi offline %s: %s", self._pending_file, exc)
            self._pending = {}

    def _save_pending_locked(self) -> None:
        """Persist while caller holds _pending_lock, using atomic replacement."""
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "queues": self._pending}
            temp_file = self._pending_file.with_suffix(".json.tmp")
            temp_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_file, self._pending_file)
        except Exception as exc:
            log.error("Không lưu được hàng đợi offline: %s", exc)

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def _bootstrap_conn(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect((self._bs_host, self._bs_port))
        sock.settimeout(RECV_TIMEOUT)
        return sock

    def register(self, peer_id, username, host, port) -> bool:
        try:
            sock = self._bootstrap_conn()
            sock.sendall(encode_msg(make_msg(
                MsgType.REGISTER,
                peer_id=peer_id,
                username=username,
                host=host,
                port=port,
            )))
            response = recv_msg(sock)
            sock.close()
            return response is not None and response["type"] == MsgType.REGISTER_OK
        except Exception as exc:
            log.error("Register thất bại: %s", exc)
            return False

    def unregister(self, peer_id):
        try:
            sock = self._bootstrap_conn()
            sock.sendall(encode_msg(make_msg(MsgType.UNREGISTER, peer_id=peer_id)))
            recv_msg(sock)
            sock.close()
        except Exception:
            pass

    def heartbeat(self, peer_id) -> bool:
        try:
            sock = self._bootstrap_conn()
            sock.sendall(encode_msg(make_msg(MsgType.HEARTBEAT, peer_id=peer_id)))
            response = recv_msg(sock)
            sock.close()
            return response is not None and response["type"] == MsgType.HEARTBEAT_OK
        except Exception:
            return False

    def get_peers(self, peer_id) -> list:
        try:
            sock = self._bootstrap_conn()
            sock.sendall(encode_msg(make_msg(MsgType.GET_PEERS, peer_id=peer_id)))
            response = recv_msg(sock)
            sock.close()
            if response and response["type"] == MsgType.PEER_LIST:
                return response["peers"]
        except Exception as exc:
            log.error("Get peers thất bại: %s", exc)
        return []

    # ------------------------------------------------------------------
    # Peer-to-peer
    # ------------------------------------------------------------------
    def send_to_peer(self, host: str, port: int, msg: dict, retries: int = 3) -> bool:
        for attempt in range(1, retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECT_TIMEOUT)
                sock.connect((host, port))
                sock.settimeout(RECV_TIMEOUT)
                sock.sendall(encode_msg(msg))
                response = recv_msg(sock)
                sock.close()
                if response is not None and response.get("type") == MsgType.ACK:
                    return True
            except Exception:
                pass
            if attempt < retries:
                time.sleep(0.5 * attempt)
        return False

    # ------------------------------------------------------------------
    # Persistent store-and-forward
    # ------------------------------------------------------------------
    def store_offline(self, username: str, msg: dict) -> None:
        key = self._queue_key(username)
        with self._pending_lock:
            queue = self._pending.setdefault(key, [])
            msg_id = msg.get("msg_id")
            if msg_id and any(item.get("msg_id") == msg_id for item in queue):
                return
            queue.append(dict(msg))
            self._save_pending_locked()

    def has_pending(self, username: str) -> bool:
        key = self._queue_key(username)
        with self._pending_lock:
            return bool(self._pending.get(key))

    def pending_count(self, username: str | None = None) -> int:
        with self._pending_lock:
            if username is None:
                return sum(len(messages) for messages in self._pending.values())
            return len(self._pending.get(self._queue_key(username), []))

    def flush_pending(self, username: str, host: str, port: int) -> int:
        """Send queued messages in order and retain every failed message on disk."""
        key = self._queue_key(username)
        with self._pending_lock:
            messages = list(self._pending.get(key, []))

        if not messages:
            return 0

        sent = 0
        failed: list[dict] = []
        for message in messages:
            if self.send_to_peer(host, port, message):
                sent += 1
            else:
                failed.append(message)

        with self._pending_lock:
            # Messages may have been appended while network I/O was in progress.
            current = self._pending.get(key, [])
            original_ids = {id(item) for item in messages}
            appended = [item for item in current if id(item) not in original_ids and item not in messages]
            remaining = failed + appended
            if remaining:
                self._pending[key] = remaining
            else:
                self._pending.pop(key, None)
            self._save_pending_locked()
        return sent
