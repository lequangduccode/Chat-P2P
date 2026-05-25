"""
Bootstrap / Tracker Server
--------------------------
Chức năng:
  - Quản lý registry các peer đang online (peer_id -> host/port/username)
  - Heartbeat timeout: xóa peer không gửi heartbeat trong PEER_TIMEOUT giây
  - Push PEER_JOINED / PEER_LEFT tới tất cả peer khi có thay đổi
  - Trả về danh sách peer khi có yêu cầu GET_PEERS
"""

import socket
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.protocol import MsgType, make_msg, encode_msg, recv_msg
from common.utils import setup_logger
from config import (BOOTSTRAP_HOST, BOOTSTRAP_PORT,
                    PEER_TIMEOUT, HEARTBEAT_INTERVAL, CONNECT_TIMEOUT, RECV_TIMEOUT)

log = setup_logger("Bootstrap")


class BootstrapServer:
    def __init__(self, host: str = BOOTSTRAP_HOST, port: int = BOOTSTRAP_PORT):
        self.host = host
        self.port = port
        # peer_id -> {host, port, username, last_seen}
        self._peers: dict = {}
        self._lock = threading.Lock()
        self.running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(100)
        log.info(f"Khởi động trên {self.host}:{self.port}")

        threading.Thread(target=self._cleanup_loop, daemon=True).start()

        while self.running:
            try:
                conn, addr = srv.accept()
                conn.settimeout(RECV_TIMEOUT)
                threading.Thread(
                    target=self._handle_conn, args=(conn,), daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    log.error(f"Accept error: {e}")

    # ------------------------------------------------------------------
    # Connection handler
    # ------------------------------------------------------------------

    def _handle_conn(self, conn: socket.socket):
        try:
            msg = recv_msg(conn)
            if not msg:
                return
            t = msg.get("type")
            if   t == MsgType.REGISTER:   self._on_register(conn, msg)
            elif t == MsgType.UNREGISTER: self._on_unregister(conn, msg)
            elif t == MsgType.GET_PEERS:  self._on_get_peers(conn, msg)
            elif t == MsgType.HEARTBEAT:  self._on_heartbeat(conn, msg)
            else:
                conn.sendall(encode_msg(make_msg(MsgType.ERROR, reason="Unknown type")))
        except Exception as e:
            log.debug(f"Handler error: {e}")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def _on_register(self, conn, msg):
        pid      = msg["peer_id"]
        username = msg["username"]
        host     = msg["host"]
        port     = msg["port"]

        with self._lock:
            self._peers[pid] = {
                "host": host, "port": port,
                "username": username, "last_seen": time.time()
            }

        log.info(f"+ {username}  ({host}:{port})")
        conn.sendall(encode_msg(make_msg(MsgType.REGISTER_OK, peer_id=pid)))

        # Thông báo cho tất cả peer còn lại
        self._push_all(
            make_msg(MsgType.PEER_JOINED,
                     peer_id=pid, username=username, host=host, port=port),
            exclude=pid
        )

    def _on_unregister(self, conn, msg):
        pid = msg["peer_id"]
        with self._lock:
            info = self._peers.pop(pid, None)

        if info:
            log.info(f"- {info['username']} (thoát)")
            conn.sendall(encode_msg(make_msg(MsgType.ACK)))
            self._push_all(
                make_msg(MsgType.PEER_LEFT,
                         peer_id=pid, username=info["username"])
            )

    def _on_get_peers(self, conn, msg):
        requester = msg.get("peer_id")
        with self._lock:
            peer_list = [
                {"peer_id": pid,
                 "host": v["host"],
                 "port": v["port"],
                 "username": v["username"]}
                for pid, v in self._peers.items()
                if pid != requester
            ]
        conn.sendall(encode_msg(make_msg(MsgType.PEER_LIST, peers=peer_list)))

    def _on_heartbeat(self, conn, msg):
        pid = msg["peer_id"]
        with self._lock:
            if pid in self._peers:
                self._peers[pid]["last_seen"] = time.time()
        conn.sendall(encode_msg(make_msg(MsgType.HEARTBEAT_OK)))

    # ------------------------------------------------------------------
    # Push notifications
    # ------------------------------------------------------------------

    def _push_all(self, msg: dict, exclude: str = None):
        with self._lock:
            targets = {
                pid: (v["host"], v["port"])
                for pid, v in self._peers.items()
                if pid != exclude
            }
        for pid, (h, p) in targets.items():
            threading.Thread(
                target=self._push_one, args=(h, p, msg), daemon=True
            ).start()

    def _push_one(self, host, port, msg):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(CONNECT_TIMEOUT)
            s.connect((host, port))
            s.sendall(encode_msg(msg))
            s.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cleanup loop – xóa peer không heartbeat
    # ------------------------------------------------------------------

    def _cleanup_loop(self):
        while self.running:
            time.sleep(HEARTBEAT_INTERVAL)
            now = time.time()
            expired = []

            with self._lock:
                for pid, info in list(self._peers.items()):
                    if now - info["last_seen"] > PEER_TIMEOUT:
                        expired.append((pid, info.copy()))
                        del self._peers[pid]

            for pid, info in expired:
                log.info(f"Timeout: {info['username']}")
                self._push_all(
                    make_msg(MsgType.PEER_LEFT,
                             peer_id=pid, username=info["username"])
                )
