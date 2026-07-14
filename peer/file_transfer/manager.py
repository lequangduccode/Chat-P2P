"""Encrypted direct file transfer over a dedicated TCP connection.

Control messages (offer/accept/reject) use the normal P2P message channel.
File bytes use a temporary direct TCP listener so large files do not block chat.
Every chunk is independently protected with AES-256-GCM.
"""
from __future__ import annotations

import hashlib
import logging
import os
import socket
import struct
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from common.protocol import encode_msg, make_msg, new_id, now_str, recv_msg

log = logging.getLogger(__name__)

FILE_OFFER = "FILE_OFFER"
FILE_ACCEPT = "FILE_ACCEPT"
FILE_REJECT = "FILE_REJECT"
FILE_CANCEL = "FILE_CANCEL"
FILE_STREAM_BEGIN = "FILE_STREAM_BEGIN"
FILE_STREAM_RESULT = "FILE_STREAM_RESULT"

CHUNK_SIZE = 256 * 1024
MAX_FILE_SIZE = 100 * 1024 * 1024
TRANSFER_TIMEOUT = 45


@dataclass
class TransferSession:
    transfer_id: str
    peer_name: str
    filename: str
    total_size: int
    direction: str
    local_path: str = ""
    sha256: str = ""
    status: str = "preparing"
    transferred: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event)
    active_socket: socket.socket | None = None


def human_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def recv_exact(sock: socket.socket, size: int) -> bytes | None:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


class FileTransferManager:
    def __init__(self, node):
        self.node = node
        self.sessions: dict[str, TransferSession] = {}
        self.incoming_offers: dict[str, dict] = {}
        self._lock = threading.RLock()

        self.on_offer: Callable[[dict], None] | None = None
        self.on_progress: Callable[[dict], None] | None = None
        self.on_completed: Callable[[dict], None] | None = None
        self.on_failed: Callable[[dict], None] | None = None
        self.on_rejected: Callable[[dict], None] | None = None

    def set_callbacks(
        self,
        *,
        offer=None,
        progress=None,
        completed=None,
        failed=None,
        rejected=None,
    ):
        self.on_offer = offer
        self.on_progress = progress
        self.on_completed = completed
        self.on_failed = failed
        self.on_rejected = rejected

    def _emit(self, callback, payload: dict):
        if callback:
            callback(dict(payload))

    def _session_payload(self, session: TransferSession, **extra) -> dict:
        payload = {
            "transfer_id": session.transfer_id,
            "peer_name": session.peer_name,
            "filename": session.filename,
            "total_size": session.total_size,
            "transferred": session.transferred,
            "direction": session.direction,
            "status": session.status,
            "local_path": session.local_path,
        }
        payload.update(extra)
        return payload

    # ------------------------------------------------------------------
    # Sender side
    # ------------------------------------------------------------------
    def offer_file(self, to_username: str, file_path: str) -> tuple[str | None, str | None]:
        path = Path(file_path)
        if not path.is_file():
            return None, "File không tồn tại hoặc không thể đọc."
        size = path.stat().st_size
        if size <= 0:
            return None, "Không thể gửi file rỗng."
        if size > MAX_FILE_SIZE:
            return None, f"File vượt giới hạn {human_size(MAX_FILE_SIZE)}."
        peer = self.node.manager.get_peer_by_name(to_username)
        if not peer:
            return None, f"Không tìm thấy peer '{to_username}'."
        if not peer.online:
            return None, "File transfer chỉ hỗ trợ peer đang online."

        transfer_id = new_id()
        session = TransferSession(
            transfer_id=transfer_id,
            peer_name=to_username,
            filename=path.name,
            total_size=size,
            direction="outgoing",
            local_path=str(path),
        )
        with self._lock:
            self.sessions[transfer_id] = session

        threading.Thread(
            target=self._prepare_and_send_offer,
            args=(session,),
            daemon=True,
            name=f"file-offer-{transfer_id[:8]}",
        ).start()
        return transfer_id, None

    def _prepare_and_send_offer(self, session: TransferSession):
        try:
            session.status = "preparing"
            self._emit(self.on_progress, self._session_payload(session))
            session.sha256 = sha256_file(Path(session.local_path))
            if session.cancel_event.is_set():
                raise RuntimeError("Đã hủy truyền file")

            peer = self.node.manager.get_peer_by_name(session.peer_name)
            if not peer or not peer.online:
                raise ConnectionError("Peer đã offline trước khi nhận đề nghị")

            offer = make_msg(
                FILE_OFFER,
                transfer_id=session.transfer_id,
                from_id=self.node.peer_id,
                from_name=self.node.username,
                to_id=peer.peer_id,
                filename=session.filename,
                size=session.total_size,
                sha256=session.sha256,
                encrypted=True,
                encryption="AES-256-GCM",
                timestamp=now_str(),
            )
            if not self.node.client.send_to_peer(peer.host, peer.port, offer):
                raise ConnectionError("Không gửi được đề nghị truyền file")

            session.status = "waiting"
            self._emit(self.on_progress, self._session_payload(session))
        except Exception as exc:
            self._fail(session, str(exc))

    def handle_accept(self, msg: dict):
        transfer_id = msg.get("transfer_id", "")
        with self._lock:
            session = self.sessions.get(transfer_id)
        if not session or session.direction != "outgoing":
            return
        host = msg.get("host")
        port = int(msg.get("port", 0))
        threading.Thread(
            target=self._send_stream,
            args=(session, host, port),
            daemon=True,
            name=f"file-send-{transfer_id[:8]}",
        ).start()

    def _send_stream(self, session: TransferSession, host: str, port: int):
        sock = None
        try:
            session.status = "connecting"
            self._emit(self.on_progress, self._session_payload(session))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TRANSFER_TIMEOUT)
            sock.connect((host, port))
            session.active_socket = sock

            begin = make_msg(
                FILE_STREAM_BEGIN,
                transfer_id=session.transfer_id,
                filename=session.filename,
                size=session.total_size,
                sha256=session.sha256,
                chunk_size=CHUNK_SIZE,
            )
            sock.sendall(encode_msg(begin))

            session.status = "transferring"
            chunk_index = 0
            with Path(session.local_path).open("rb") as handle:
                while True:
                    if session.cancel_event.is_set():
                        raise RuntimeError("Đã hủy truyền file")
                    chunk = handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    aad = f"{session.transfer_id}:{chunk_index}".encode("utf-8")
                    packet = self.node.crypto.encrypt_bytes(chunk, aad)
                    sock.sendall(struct.pack(">I", len(packet)))
                    sock.sendall(packet)
                    session.transferred += len(chunk)
                    self._emit(self.on_progress, self._session_payload(session))
                    chunk_index += 1

            sock.sendall(struct.pack(">I", 0))
            result = recv_msg(sock)
            if not result or result.get("type") != FILE_STREAM_RESULT:
                raise ConnectionError("Không nhận được xác nhận hoàn tất")
            if not result.get("ok"):
                raise IOError(result.get("error", "Peer nhận báo lỗi"))
            session.status = "completed"
            self._emit(self.on_completed, self._session_payload(session))
        except Exception as exc:
            self._fail(session, str(exc))
        finally:
            session.active_socket = None
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Receiver side
    # ------------------------------------------------------------------
    def handle_offer(self, msg: dict):
        transfer_id = msg.get("transfer_id", "")
        try:
            size = int(msg.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if not transfer_id or not msg.get("filename") or size <= 0 or size > MAX_FILE_SIZE:
            return
        with self._lock:
            self.incoming_offers[transfer_id] = dict(msg)
        self._emit(self.on_offer, msg)

    def accept_offer(self, transfer_id: str, save_path: str) -> str | None:
        with self._lock:
            offer = self.incoming_offers.get(transfer_id)
        if not offer:
            return "Đề nghị truyền file không còn tồn tại."

        destination = Path(save_path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"Không thể tạo thư mục lưu file: {exc}"

        session = TransferSession(
            transfer_id=transfer_id,
            peer_name=offer.get("from_name", "Unknown"),
            filename=offer["filename"],
            total_size=int(offer["size"]),
            direction="incoming",
            local_path=str(destination),
            sha256=offer.get("sha256", ""),
            status="waiting",
        )
        with self._lock:
            self.sessions[transfer_id] = session

        threading.Thread(
            target=self._receive_stream,
            args=(session, offer),
            daemon=True,
            name=f"file-recv-{transfer_id[:8]}",
        ).start()
        return None

    def _receive_stream(self, session: TransferSession, offer: dict):
        listener = None
        conn = None
        temp_path = Path(session.local_path + ".part")
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.node.host, 0))
            listener.listen(1)
            listener.settimeout(TRANSFER_TIMEOUT)
            transfer_port = listener.getsockname()[1]

            peer = self.node.manager.get_peer_by_name(session.peer_name)
            if not peer or not peer.online:
                raise ConnectionError("Peer gửi đã offline")

            accept_msg = make_msg(
                FILE_ACCEPT,
                transfer_id=session.transfer_id,
                from_id=self.node.peer_id,
                from_name=self.node.username,
                to_id=peer.peer_id,
                host=self.node.host,
                port=transfer_port,
            )
            if not self.node.client.send_to_peer(peer.host, peer.port, accept_msg):
                raise ConnectionError("Không gửi được phản hồi chấp nhận")

            session.status = "waiting"
            self._emit(self.on_progress, self._session_payload(session))
            conn, _ = listener.accept()
            conn.settimeout(TRANSFER_TIMEOUT)
            session.active_socket = conn

            begin = recv_msg(conn)
            if (
                not begin
                or begin.get("type") != FILE_STREAM_BEGIN
                or begin.get("transfer_id") != session.transfer_id
            ):
                raise ValueError("Header truyền file không hợp lệ")

            session.status = "transferring"
            digest = hashlib.sha256()
            received = 0
            chunk_index = 0
            with temp_path.open("wb") as output:
                while True:
                    if session.cancel_event.is_set():
                        raise RuntimeError("Đã hủy nhận file")
                    raw_length = recv_exact(conn, 4)
                    if raw_length is None:
                        raise ConnectionError("Kết nối bị đóng giữa chừng")
                    packet_length = struct.unpack(">I", raw_length)[0]
                    if packet_length == 0:
                        break
                    if packet_length > CHUNK_SIZE + 128:
                        raise ValueError("Chunk file vượt kích thước cho phép")
                    packet = recv_exact(conn, packet_length)
                    if packet is None:
                        raise ConnectionError("Không nhận đủ dữ liệu chunk")
                    aad = f"{session.transfer_id}:{chunk_index}".encode("utf-8")
                    plaintext = self.node.crypto.decrypt_bytes(packet, aad)
                    output.write(plaintext)
                    digest.update(plaintext)
                    received += len(plaintext)
                    session.transferred = received
                    self._emit(self.on_progress, self._session_payload(session))
                    chunk_index += 1

            actual_hash = digest.hexdigest()
            if received != session.total_size:
                raise IOError(
                    f"Kích thước không khớp: nhận {received}, dự kiến {session.total_size}"
                )
            if session.sha256 and actual_hash != session.sha256:
                raise IOError("SHA-256 không khớp; file có thể đã bị thay đổi")

            final_path = Path(session.local_path)
            if final_path.exists():
                final_path = self._unique_path(final_path)
                session.local_path = str(final_path)
            os.replace(temp_path, final_path)
            conn.sendall(encode_msg(make_msg(FILE_STREAM_RESULT, ok=True)))
            session.status = "completed"
            self._emit(self.on_completed, self._session_payload(session))
        except Exception as exc:
            try:
                if conn:
                    conn.sendall(encode_msg(make_msg(FILE_STREAM_RESULT, ok=False, error=str(exc))))
            except Exception:
                pass
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._fail(session, str(exc))
        finally:
            session.active_socket = None
            for sock in (conn, listener):
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass
            with self._lock:
                self.incoming_offers.pop(session.transfer_id, None)

    def reject_offer(self, transfer_id: str, reason: str = "Người nhận từ chối"):
        with self._lock:
            offer = self.incoming_offers.pop(transfer_id, None)
        if not offer:
            return
        peer = self.node.manager.get_peer_by_name(offer.get("from_name", ""))
        if peer and peer.online:
            self.node.client.send_to_peer(
                peer.host,
                peer.port,
                make_msg(
                    FILE_REJECT,
                    transfer_id=transfer_id,
                    from_name=self.node.username,
                    reason=reason,
                ),
            )

    def handle_reject(self, msg: dict):
        transfer_id = msg.get("transfer_id", "")
        with self._lock:
            session = self.sessions.get(transfer_id)
        if not session:
            return
        session.status = "rejected"
        payload = self._session_payload(
            session, reason=msg.get("reason", "Người nhận từ chối")
        )
        self._emit(self.on_rejected, payload)

    # ------------------------------------------------------------------
    # Cancellation and errors
    # ------------------------------------------------------------------
    def cancel(self, transfer_id: str):
        with self._lock:
            session = self.sessions.get(transfer_id)
        if not session:
            return
        session.cancel_event.set()
        session.status = "cancelled"
        if session.active_socket:
            try:
                session.active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                session.active_socket.close()
            except OSError:
                pass
        peer = self.node.manager.get_peer_by_name(session.peer_name)
        if peer and peer.online:
            self.node.client.send_to_peer(
                peer.host,
                peer.port,
                make_msg(
                    FILE_CANCEL,
                    transfer_id=transfer_id,
                    from_name=self.node.username,
                ),
                retries=1,
            )
        self._emit(self.on_failed, self._session_payload(session, error="Đã hủy truyền file"))

    def handle_cancel(self, msg: dict):
        transfer_id = msg.get("transfer_id", "")
        with self._lock:
            session = self.sessions.get(transfer_id)
        if session:
            session.cancel_event.set()
            if session.active_socket:
                try:
                    session.active_socket.close()
                except OSError:
                    pass

    def _fail(self, session: TransferSession, error: str):
        if session.status != "cancelled":
            session.status = "failed"
        self._emit(self.on_failed, self._session_payload(session, error=error))

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        index = 1
        while True:
            candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
            if not candidate.exists():
                return candidate
            index += 1
