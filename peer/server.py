"""PeerServer – TCP server for chat/control messages."""
from __future__ import annotations

import logging
import socket
import threading

from common.protocol import MsgType, encode_msg, make_msg, recv_msg

log = logging.getLogger(__name__)

_ACK_TYPES = {
    MsgType.DIRECT_MSG,
    MsgType.GROUP_MSG,
    MsgType.GROUP_INVITE,
    MsgType.PEER_JOINED,
    MsgType.PEER_LEFT,
    "FILE_SHARE",
    "FILE_DOWNLOAD_REQUEST",
    "FILE_CANCEL",
}


class PeerServer:
    def __init__(self, host: str, port: int, on_message):
        self.host = host
        self.port = port
        self.on_message = on_message
        self._sock: socket.socket | None = None
        self.running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(50)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        log.info("Peer server đang lắng nghe %s:%s", self.host, self.port)

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def _accept_loop(self):
        while self.running:
            try:
                conn, _ = self._sock.accept()
                conn.settimeout(10)
                threading.Thread(
                    target=self._handle_conn, args=(conn,), daemon=True
                ).start()
            except Exception:
                if self.running:
                    log.debug("Accept loop interrupted")

    def _handle_conn(self, conn: socket.socket):
        try:
            msg = recv_msg(conn)
            if msg is None:
                return
            if msg.get("type") in _ACK_TYPES:
                try:
                    conn.sendall(encode_msg(make_msg(MsgType.ACK)))
                except OSError:
                    pass
        except Exception as exc:
            log.debug("recv error: %s", exc)
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass

        try:
            self.on_message(msg)
        except Exception as exc:
            log.exception("on_message error: %s", exc)
