"""Encrypted on-demand file sharing for direct and group conversations.

A FILE_SHARE control message publishes metadata into a conversation.
No file bytes are transferred at that point. A recipient explicitly clicks
Download, opens a temporary TCP listener, and sends FILE_DOWNLOAD_REQUEST to
the original sender. The sender then streams encrypted chunks directly.
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

FILE_SHARE = "FILE_SHARE"
FILE_DOWNLOAD_REQUEST = "FILE_DOWNLOAD_REQUEST"
FILE_CANCEL = "FILE_CANCEL"
FILE_STREAM_BEGIN = "FILE_STREAM_BEGIN"
FILE_STREAM_RESULT = "FILE_STREAM_RESULT"

CHUNK_SIZE = 256 * 1024
MAX_FILE_SIZE = 100 * 1024 * 1024
TRANSFER_TIMEOUT = 60


@dataclass
class SharedFile:
    share_id: str
    filename: str
    total_size: int
    local_path: str
    sha256: str
    conversation_type: str
    target_name: str
    group_id: str = ""


@dataclass
class DownloadSession:
    request_id: str
    share_id: str
    peer_name: str
    filename: str
    total_size: int
    local_path: str
    direction: str = "incoming"
    sha256: str = ""
    status: str = "available"
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
        self.shared_files: dict[str, SharedFile] = {}
        self.incoming_shares: dict[str, dict] = {}
        self.sessions: dict[str, DownloadSession] = {}
        self._lock = threading.RLock()

        self.on_offer: Callable[[dict], None] | None = None
        self.on_progress: Callable[[dict], None] | None = None
        self.on_completed: Callable[[dict], None] | None = None
        self.on_failed: Callable[[dict], None] | None = None
        self.on_rejected: Callable[[dict], None] | None = None

    def set_callbacks(
        self, *, offer=None, progress=None, completed=None, failed=None, rejected=None
    ):
        self.on_offer = offer
        self.on_progress = progress
        self.on_completed = completed
        self.on_failed = failed
        self.on_rejected = rejected

    def _emit(self, callback, payload: dict):
        if callback:
            callback(dict(payload))

    def _session_payload(self, session: DownloadSession, **extra) -> dict:
        payload = {
            "transfer_id": session.share_id,
            "request_id": session.request_id,
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
    # Publish file metadata
    # ------------------------------------------------------------------
    def share_direct(self, to_username: str, file_path: str):
        return self._share(file_path, "direct", to_username)

    def share_group(self, group_name: str, file_path: str):
        return self._share(file_path, "group", group_name)

    def _share(self, file_path: str, conversation_type: str, target_name: str):
        path = Path(file_path)
        if not path.is_file():
            return None, "File không tồn tại hoặc không thể đọc."
        size = path.stat().st_size
        if size <= 0:
            return None, "Không thể chia sẻ file rỗng."
        if size > MAX_FILE_SIZE:
            return None, f"File vượt giới hạn {human_size(MAX_FILE_SIZE)}."

        if conversation_type == "direct":
            peer = self.node.manager.get_peer_by_name(target_name)
            if not peer:
                return None, f"Không tìm thấy peer '{target_name}'."
            recipients = [peer]
            group_id = ""
        else:
            group = self.node.manager.get_group_by_name(target_name)
            if not group:
                return None, f"Không tìm thấy nhóm '{target_name}'."
            group_id = group.group_id
            recipients = []
            for member_id in group.members:
                if member_id == self.node.peer_id:
                    continue
                peer = self.node.manager.get_peer(member_id)
                if peer:
                    recipients.append(peer)

        share_id = new_id()
        shared = SharedFile(
            share_id=share_id,
            filename=path.name,
            total_size=size,
            local_path=str(path),
            sha256="",
            conversation_type=conversation_type,
            target_name=target_name,
            group_id=group_id,
        )
        with self._lock:
            self.shared_files[share_id] = shared

        threading.Thread(
            target=self._prepare_share,
            args=(shared, recipients),
            daemon=True,
            name=f"file-share-{share_id[:8]}",
        ).start()
        return share_id, None

    def _prepare_share(self, shared: SharedFile, recipients: list):
        try:
            self._emit(self.on_progress, {
                "transfer_id": shared.share_id,
                "filename": shared.filename,
                "total_size": shared.total_size,
                "transferred": 0,
                "direction": "outgoing",
                "status": "preparing",
                "local_path": shared.local_path,
            })
            shared.sha256 = sha256_file(Path(shared.local_path))
            message = make_msg(
                FILE_SHARE,
                share_id=shared.share_id,
                transfer_id=shared.share_id,
                from_id=self.node.peer_id,
                from_name=self.node.username,
                filename=shared.filename,
                size=shared.total_size,
                sha256=shared.sha256,
                conversation_type=shared.conversation_type,
                target_name=shared.target_name,
                group_id=shared.group_id,
                group_name=shared.target_name if shared.conversation_type == "group" else "",
                encrypted=True,
                encryption="AES-256-GCM",
                timestamp=now_str(),
            )

            queued = []
            failed = []
            for peer in recipients:
                if not peer.online:
                    self.node.client.store_offline(peer.username, message)
                    queued.append(peer.username)
                elif not self.node.client.send_to_peer(peer.host, peer.port, message):
                    self.node.client.store_offline(peer.username, message)
                    queued.append(peer.username)

            self._emit(self.on_completed, {
                "transfer_id": shared.share_id,
                "filename": shared.filename,
                "total_size": shared.total_size,
                "transferred": 0,
                "direction": "outgoing",
                "status": "shared",
                "local_path": shared.local_path,
                "queued_for": queued,
                "failed_for": failed,
            })
        except Exception as exc:
            with self._lock:
                self.shared_files.pop(shared.share_id, None)
            self._emit(self.on_failed, {
                "transfer_id": shared.share_id,
                "filename": shared.filename,
                "total_size": shared.total_size,
                "direction": "outgoing",
                "status": "failed",
                "local_path": shared.local_path,
                "error": str(exc),
            })

    def handle_share(self, msg: dict):
        share_id = msg.get("share_id") or msg.get("transfer_id", "")
        try:
            size = int(msg.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if not share_id or not msg.get("filename") or size <= 0 or size > MAX_FILE_SIZE:
            return
        msg = dict(msg)
        msg["share_id"] = share_id
        msg["transfer_id"] = share_id
        with self._lock:
            self.incoming_shares[share_id] = msg
        self._emit(self.on_offer, msg)

    # ------------------------------------------------------------------
    # Recipient explicitly requests a download
    # ------------------------------------------------------------------
    def download(self, share_id: str, save_path: str) -> str | None:
        with self._lock:
            offer = self.incoming_shares.get(share_id)
        if not offer:
            return "Thông tin file không còn tồn tại."
        sender = offer.get("from_name", "")
        peer = self.node.manager.get_peer_by_name(sender)
        if not peer or not peer.online:
            return "Người gửi đang offline. Hãy thử tải lại khi họ online."

        request_id = new_id()
        session = DownloadSession(
            request_id=request_id,
            share_id=share_id,
            peer_name=sender,
            filename=offer["filename"],
            total_size=int(offer["size"]),
            local_path=save_path,
            sha256=offer.get("sha256", ""),
            status="connecting",
        )
        with self._lock:
            self.sessions[request_id] = session

        threading.Thread(
            target=self._receive_download,
            args=(session, peer),
            daemon=True,
            name=f"file-download-{request_id[:8]}",
        ).start()
        return None

    def _receive_download(self, session: DownloadSession, sender_peer):
        listener = None
        conn = None
        temp_path = Path(session.local_path + ".part")
        try:
            destination = Path(session.local_path)
            destination.parent.mkdir(parents=True, exist_ok=True)

            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.node.host, 0))
            listener.listen(1)
            listener.settimeout(TRANSFER_TIMEOUT)
            port = listener.getsockname()[1]

            request = make_msg(
                FILE_DOWNLOAD_REQUEST,
                share_id=session.share_id,
                transfer_id=session.share_id,
                request_id=session.request_id,
                from_id=self.node.peer_id,
                from_name=self.node.username,
                host=self.node.host,
                port=port,
            )
            if not self.node.client.send_to_peer(
                sender_peer.host, sender_peer.port, request
            ):
                raise ConnectionError("Không gửi được yêu cầu tải tới người chia sẻ")

            session.status = "waiting"
            self._emit(self.on_progress, self._session_payload(session))
            conn, _ = listener.accept()
            conn.settimeout(TRANSFER_TIMEOUT)
            session.active_socket = conn

            begin = recv_msg(conn)
            if (
                not begin
                or begin.get("type") != FILE_STREAM_BEGIN
                or begin.get("request_id") != session.request_id
                or begin.get("share_id") != session.share_id
            ):
                raise ValueError("Header truyền file không hợp lệ")

            session.status = "transferring"
            digest = hashlib.sha256()
            received = 0
            chunk_index = 0
            with temp_path.open("wb") as output:
                while True:
                    if session.cancel_event.is_set():
                        raise RuntimeError("Đã hủy tải file")
                    raw_length = recv_exact(conn, 4)
                    if raw_length is None:
                        raise ConnectionError("Kết nối bị đóng giữa chừng")
                    packet_length = struct.unpack(">I", raw_length)[0]
                    if packet_length == 0:
                        break
                    if packet_length > CHUNK_SIZE + 128:
                        raise ValueError("Chunk vượt kích thước cho phép")
                    packet = recv_exact(conn, packet_length)
                    if packet is None:
                        raise ConnectionError("Không nhận đủ dữ liệu chunk")
                    aad = (
                        f"{session.share_id}:{session.request_id}:{chunk_index}"
                    ).encode("utf-8")
                    plaintext = self.node.crypto.decrypt_bytes(packet, aad)
                    output.write(plaintext)
                    digest.update(plaintext)
                    received += len(plaintext)
                    session.transferred = received
                    self._emit(self.on_progress, self._session_payload(session))
                    chunk_index += 1

            if received != session.total_size:
                raise IOError(
                    f"Kích thước không khớp: nhận {received}, "
                    f"dự kiến {session.total_size}"
                )
            actual_hash = digest.hexdigest()
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
                    conn.sendall(
                        encode_msg(make_msg(FILE_STREAM_RESULT, ok=False, error=str(exc)))
                    )
            except Exception:
                pass
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            session.status = "cancelled" if session.cancel_event.is_set() else "failed"
            self._emit(
                self.on_failed,
                self._session_payload(session, error=str(exc)),
            )
        finally:
            session.active_socket = None
            for sock in (conn, listener):
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass

    # ------------------------------------------------------------------
    # Original sender serves any number of independent download requests
    # ------------------------------------------------------------------
    def handle_download_request(self, msg: dict):
        share_id = msg.get("share_id") or msg.get("transfer_id", "")
        request_id = msg.get("request_id", "")
        with self._lock:
            shared = self.shared_files.get(share_id)
        if not shared or not request_id:
            return
        threading.Thread(
            target=self._serve_download,
            args=(shared, msg),
            daemon=True,
            name=f"file-serve-{request_id[:8]}",
        ).start()

    def _serve_download(self, shared: SharedFile, request: dict):
        sock = None
        try:
            path = Path(shared.local_path)
            if not path.is_file():
                raise FileNotFoundError(
                    "File gốc đã bị di chuyển hoặc xóa khỏi máy người gửi"
                )
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TRANSFER_TIMEOUT)
            sock.connect((request["host"], int(request["port"])))

            request_id = request["request_id"]
            sock.sendall(encode_msg(make_msg(
                FILE_STREAM_BEGIN,
                share_id=shared.share_id,
                request_id=request_id,
                filename=shared.filename,
                size=shared.total_size,
                sha256=shared.sha256,
                chunk_size=CHUNK_SIZE,
            )))

            chunk_index = 0
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    aad = (
                        f"{shared.share_id}:{request_id}:{chunk_index}"
                    ).encode("utf-8")
                    packet = self.node.crypto.encrypt_bytes(chunk, aad)
                    sock.sendall(struct.pack(">I", len(packet)))
                    sock.sendall(packet)
                    chunk_index += 1
            sock.sendall(struct.pack(">I", 0))
            result = recv_msg(sock)
            if not result or not result.get("ok"):
                log.warning(
                    "Peer %s không hoàn tất tải file %s: %s",
                    request.get("from_name"),
                    shared.filename,
                    (result or {}).get("error", "không có ACK"),
                )
        except Exception as exc:
            log.warning("Không thể phục vụ lượt tải file: %s", exc)
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def cancel(self, request_or_share_id: str):
        with self._lock:
            sessions = [
                session
                for session in self.sessions.values()
                if session.request_id == request_or_share_id
                or session.share_id == request_or_share_id
            ]
        for session in sessions:
            session.cancel_event.set()
            if session.active_socket:
                try:
                    session.active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    session.active_socket.close()
                except OSError:
                    pass

    def handle_cancel(self, msg: dict):
        self.cancel(msg.get("request_id") or msg.get("share_id", ""))

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
