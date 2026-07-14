"""
PeerServer – TCP server lắng nghe kết nối đến từ peer khác hoặc bootstrap.
Mỗi kết nối được xử lý trong một thread riêng.
Gọi callback on_message(msg) khi nhận được tin nhắn.
"""

import socket
import threading
import logging

from common.protocol import MsgType, make_msg, encode_msg, recv_msg

log = logging.getLogger(__name__)


class PeerServer:
    def __init__(self, host: str, port: int, on_message):
        self.host = host
        self.port = port
        self.on_message = on_message   # callable(msg: dict)
        self._sock: socket.socket | None = None
        self.running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(50)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        log.info(f"Peer server đang lắng nghe {self.host}:{self.port}")

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self._sock.accept()
                conn.settimeout(10)
                threading.Thread(
                    target=self._handle_conn, args=(conn,), daemon=True
                ).start()
            except Exception:
                if self.running:
                    log.debug("Accept loop interrupted")

    def _handle_conn(self, conn: socket.socket):
        msg = None
        try:
            msg = recv_msg(conn)
        except Exception as e:
            log.debug(f"recv error: {e}")
        finally:
            if msg is None:
                conn.close()
                return

        msg_type = msg.get("type")

        # Gửi ACK — bọc try/except riêng vì sender có thể đã đóng socket
        # (ví dụ: bootstrap push PEER_JOINED rồi đóng ngay, không chờ ACK)
        if msg_type in (
            MsgType.DIRECT_MSG, MsgType.GROUP_MSG, MsgType.FILE_MSG,
            MsgType.GROUP_INVITE, MsgType.PEER_JOINED, MsgType.PEER_LEFT,
        ):
            try:
                conn.sendall(encode_msg(make_msg(MsgType.ACK)))
            except Exception:
                pass  # ACK thất bại không ảnh hưởng việc xử lý message

        conn.close()

        # Xử lý message sau khi đã đóng socket — luôn chạy dù ACK thất bại
        try:
            self.on_message(msg)
        except Exception as e:
            log.debug(f"on_message error: {e}")
