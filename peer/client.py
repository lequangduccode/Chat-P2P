"""
PeerClient – phần gửi tin của peer node.

Nhiệm vụ:
  - Giao tiếp với bootstrap (register / unregister / heartbeat / get_peers)
  - Gửi tin nhắn tới peer khác
  - Lưu offline messages (store-and-forward): nếu peer đích không phản hồi,
    tin nhắn được giữ lại và tự động gửi khi peer đó online trở lại.
"""

import socket
import threading
import logging

from common.protocol import MsgType, make_msg, encode_msg, recv_msg
from config import CONNECT_TIMEOUT, RECV_TIMEOUT

log = logging.getLogger(__name__)


class PeerClient:
    def __init__(self, bootstrap_host: str, bootstrap_port: int):
        self._bs_host = bootstrap_host
        self._bs_port = bootstrap_port
        # peer_id -> list[dict]  (tin nhắn chờ gửi khi peer offline)
        self._pending: dict[str, list] = {}
        self._pending_lock = threading.Lock()

    # ------------------------------------------------------------------ Bootstrap

    def _bootstrap_conn(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(CONNECT_TIMEOUT)
        s.connect((self._bs_host, self._bs_port))
        s.settimeout(RECV_TIMEOUT)
        return s

    def register(self, peer_id, username, host, port) -> bool:
        try:
            s = self._bootstrap_conn()
            s.sendall(encode_msg(make_msg(
                MsgType.REGISTER,
                peer_id=peer_id, username=username,
                host=host, port=port,
            )))
            resp = recv_msg(s)
            s.close()
            return resp is not None and resp["type"] == MsgType.REGISTER_OK
        except Exception as e:
            log.error(f"Register thất bại: {e}")
            return False

    def unregister(self, peer_id):
        try:
            s = self._bootstrap_conn()
            s.sendall(encode_msg(make_msg(MsgType.UNREGISTER, peer_id=peer_id)))
            recv_msg(s)
            s.close()
        except Exception:
            pass

    def heartbeat(self, peer_id) -> bool:
        try:
            s = self._bootstrap_conn()
            s.sendall(encode_msg(make_msg(MsgType.HEARTBEAT, peer_id=peer_id)))
            resp = recv_msg(s)
            s.close()
            return resp is not None and resp["type"] == MsgType.HEARTBEAT_OK
        except Exception:
            return False

    def get_peers(self, peer_id) -> list:
        try:
            s = self._bootstrap_conn()
            s.sendall(encode_msg(make_msg(MsgType.GET_PEERS, peer_id=peer_id)))
            resp = recv_msg(s)
            s.close()
            if resp and resp["type"] == MsgType.PEER_LIST:
                return resp["peers"]
        except Exception as e:
            log.error(f"Get peers thất bại: {e}")
        return []

    # ------------------------------------------------------------------ Peer-to-peer

    def send_to_peer(self, host: str, port: int, msg: dict,
                     retries: int = 3) -> bool:
        """Gửi message tới peer, thử lại tối đa `retries` lần, trả về True khi có ACK."""
        for attempt in range(1, retries + 1):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(CONNECT_TIMEOUT)
                s.connect((host, port))
                s.settimeout(RECV_TIMEOUT)
                s.sendall(encode_msg(msg))
                resp = recv_msg(s)
                s.close()
                if resp is not None and resp.get("type") == MsgType.ACK:
                    return True
            except Exception:
                pass
            if attempt < retries:
                import time
                time.sleep(0.5 * attempt)   # back-off: 0.5s, 1s
        return False

    # ------------------------------------------------------------------ Store-and-forward

    def store_offline(self, peer_id: str, msg: dict):
        with self._pending_lock:
            self._pending.setdefault(peer_id, []).append(msg)

    def has_pending(self, peer_id: str) -> bool:
        with self._pending_lock:
            return bool(self._pending.get(peer_id))

    def flush_pending(self, peer_id: str, host: str, port: int) -> int:
        """Gửi tất cả tin nhắn offline cho peer_id. Trả về số tin nhắn gửi thành công."""
        with self._pending_lock:
            msgs = self._pending.pop(peer_id, [])

        sent = 0
        failed = []
        for msg in msgs:
            if self.send_to_peer(host, port, msg):
                sent += 1
            else:
                failed.append(msg)

        if failed:
            with self._pending_lock:
                self._pending.setdefault(peer_id, []).extend(failed)

        return sent
