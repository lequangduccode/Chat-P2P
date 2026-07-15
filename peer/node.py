"""PeerNode – bộ điều phối trung tâm của một peer."""
from __future__ import annotations

import logging
import threading
import time

from common.protocol import MsgType, make_msg, new_id, now_str
from common.utils import get_local_ip
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, HEARTBEAT_INTERVAL
from peer.client import PeerClient
from peer.churn import ChurnController
from peer.crypto import MessageCrypto, MessageDecryptionError
from peer.peer_manager import PeerManager
from peer.file_transfer.manager import (
    FILE_CANCEL,
    FILE_DOWNLOAD_REQUEST,
    FILE_SHARE,
    FileTransferManager,
)
from peer.server import PeerServer

log = logging.getLogger(__name__)


class PeerNode:
    def __init__(
        self,
        username: str,
        port: int,
        bootstrap_host: str = BOOTSTRAP_HOST,
        bootstrap_port: int = BOOTSTRAP_PORT,
        encryption_key: str = "p2p-chat-demo-2026",
    ):
        self.peer_id = new_id()
        self.username = username
        self.host = get_local_ip()
        self.port = port
        self.manager = PeerManager()
        self.client = PeerClient(bootstrap_host, bootstrap_port, storage_owner=username)
        self.crypto = MessageCrypto(encryption_key)
        self.server = PeerServer(self.host, self.port, self._on_message)
        self.file_transfer = FileTransferManager(self)
        self.churn = ChurnController(self)
        self._running = False
        self._online = False
        self._lifecycle_lock = threading.RLock()
        self._display_cb = None

    def set_display(self, callback):
        self._display_cb = callback

    def _display(self, text: str):
        if self._display_cb:
            self._display_cb(text)
        else:
            print(text)

    @property
    def is_online(self) -> bool:
        return self._online

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self._running:
                return self._online
            self._running = True

        if not self.go_online():
            self._running = False
            return False

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        log.info(
            "Peer '%s' sẵn sàng (id=%s…, %s:%s)",
            self.username,
            self.peer_id[:8],
            self.host,
            self.port,
        )
        return True

    def go_offline(self) -> bool:
        """Temporarily leave the P2P network while the GUI keeps running."""
        with self._lifecycle_lock:
            if not self._online:
                return True

            for transfer_id in list(self.file_transfer.sessions):
                session = self.file_transfer.sessions.get(transfer_id)
                if session and session.status in {
                    "preparing", "waiting", "connecting", "transferring"
                }:
                    self.file_transfer.cancel(transfer_id)

            self.client.unregister(self.peer_id)
            self.server.stop()
            self._online = False
            self._display("\n >> Peer đang offline do mô phỏng churn")
            return True

    def go_online(self) -> bool:
        """Open the listening socket and register the same peer again."""
        with self._lifecycle_lock:
            if self._online:
                return True

            try:
                self.server.start()
            except OSError as exc:
                log.warning("Không thể mở peer server: %s", exc)
                return False

            if not self.client.register(
                self.peer_id, self.username, self.host, self.port
            ):
                self.server.stop()
                log.warning("Không thể register peer với bootstrap")
                return False

            self._online = True
            self._refresh_peers()
            self._display("\n >> Peer đã online lại")
            return True

    def stop(self):
        self.churn.stop(reconnect=False)
        self._running = False

        for transfer_id in list(self.file_transfer.sessions):
            session = self.file_transfer.sessions.get(transfer_id)
            if session and session.status in {
                "preparing", "waiting", "connecting", "transferring"
            }:
                self.file_transfer.cancel(transfer_id)

        with self._lifecycle_lock:
            if self._online:
                self.client.unregister(self.peer_id)
            self._online = False
            self.server.stop()

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            if self._running and self._online and not self.client.heartbeat(self.peer_id):
                log.warning("Heartbeat thất bại")

    def _refresh_loop(self):
        while self._running:
            time.sleep(30)
            if self._running and self._online:
                self._refresh_peers()

    def _refresh_peers(self):
        peers = self.client.get_peers(self.peer_id)
        self.manager.set_peers(peers)
        # Covers both cases: the recipient is already online when this sender
        # restarts, and PEER_JOINED was missed while the app was disconnected.
        for peer in self.manager.all_peers():
            self._flush_for_peer(peer.username, peer.host, peer.port)

    def _flush_for_peer(self, username: str, host: str, port: int) -> int:
        if not self.client.has_pending(username):
            return 0
        sent = self.client.flush_pending(username, host, port)
        if sent:
            self._display(f"\n >> Đã chuyển tiếp {sent} tin nhắn đang chờ tới {username}")
        return sent

    def _on_message(self, msg: dict):
        # Decrypt only message types that carry user content. Bootstrap events
        # and group membership messages remain ordinary routing metadata.
        if msg.get("type") in (MsgType.DIRECT_MSG, MsgType.GROUP_MSG):
            try:
                msg = self.crypto.decrypt_content(msg)
            except MessageDecryptionError as exc:
                sender = msg.get("from_name", "peer không xác định")
                self._display(f"\n [MÃ HÓA] Không thể đọc tin từ {sender}: {exc}")
                return
        handlers = {
            MsgType.PEER_JOINED: self._on_peer_joined,
            MsgType.PEER_LEFT: self._on_peer_left,
            MsgType.DIRECT_MSG: self._on_direct_msg,
            MsgType.GROUP_MSG: self._on_group_msg,
            MsgType.GROUP_INVITE: self._on_group_invite,
            FILE_SHARE: self.file_transfer.handle_share,
            FILE_DOWNLOAD_REQUEST: self.file_transfer.handle_download_request,
            FILE_CANCEL: self.file_transfer.handle_cancel,
        }
        handler = handlers.get(msg.get("type"))
        if handler:
            handler(msg)

    def _on_peer_joined(self, msg):
        peer_id = msg["peer_id"]
        username = msg["username"]
        host = msg["host"]
        port = msg["port"]
        self.manager.add_peer(peer_id, username, host, port)
        self._display(f"\n >> {username} vừa tham gia mạng")
        self._flush_for_peer(username, host, port)

    def _on_peer_left(self, msg):
        peer_id, username = msg["peer_id"], msg["username"]
        self.manager.mark_offline(peer_id)
        self._display(f"\n >> {username} đã rời mạng")

    def _on_direct_msg(self, msg):
        self._display(f"\n[{msg.get('timestamp', '')}] {msg['from_name']} → bạn: {msg['content']}")

    def _on_group_msg(self, msg):
        self._display(
            f"\n[{msg.get('timestamp', '')}] [{msg['group_name']}] "
            f"{msg['from_name']}: {msg['content']}"
        )

    def _on_group_invite(self, msg):
        self.manager.add_group(msg["group_id"], msg["group_name"], msg["members"])
        self._display(
            f"\n >> {msg['from_name']} đã thêm bạn vào nhóm '{msg['group_name']}' "
            f"({len(msg['members'])} thành viên)"
        )

    def send_direct(self, to_username: str, content: str) -> str | None:
        if not self._online:
            return "Peer hiện offline do mô phỏng churn."
        peer = self.manager.get_peer_by_name(to_username)
        if not peer:
            return f"Không tìm thấy peer '{to_username}'"
        message = make_msg(
            MsgType.DIRECT_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=self.username,
            to_id=peer.peer_id,
            content=content,
            timestamp=now_str(),
        )
        message = self.crypto.encrypt_content(message)
        if not peer.online:
            self.client.store_offline(peer.username, message)
            return f"'{to_username}' hiện offline. Tin nhắn đã được lưu bền vững."
        if self.client.send_to_peer(peer.host, peer.port, message):
            return None
        self.client.store_offline(peer.username, message)
        return f"'{to_username}' không phản hồi. Tin nhắn đã được lưu bền vững."

    def send_group(self, group_name: str, content: str) -> str | None:
        if not self._online:
            return "Peer hiện offline do mô phỏng churn."
        group = self.manager.get_group_by_name(group_name)
        if not group:
            return f"Không tìm thấy nhóm '{group_name}'"
        message = make_msg(
            MsgType.GROUP_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=self.username,
            group_id=group.group_id,
            group_name=group.group_name,
            content=content,
            timestamp=now_str(),
        )
        message = self.crypto.encrypt_content(message)
        offline = []
        for member_id in group.members:
            if member_id == self.peer_id:
                continue
            peer = self.manager.get_peer(member_id)
            if not peer:
                continue
            if not peer.online or not self.client.send_to_peer(peer.host, peer.port, message):
                self.client.store_offline(peer.username, message)
                offline.append(peer.username)
        if offline:
            return "Tin nhóm đã lưu cho peer offline: " + ", ".join(offline)
        return None

    def create_group(self, group_name: str, member_names: list) -> str | None:
        if not self._online:
            return "Peer hiện offline do mô phỏng churn."
        group_id = new_id()
        members = [self.peer_id]
        peers = []
        missing = []
        for name in member_names:
            peer = self.manager.get_peer_by_name(name)
            if peer:
                members.append(peer.peer_id)
                peers.append(peer)
            else:
                missing.append(name)
        if missing:
            return "Không tìm thấy peer: " + ", ".join(missing)
        self.manager.add_group(group_id, group_name, members)
        invite = make_msg(
            MsgType.GROUP_INVITE,
            from_id=self.peer_id,
            from_name=self.username,
            group_id=group_id,
            group_name=group_name,
            members=members,
        )
        for peer in peers:
            if not peer.online or not self.client.send_to_peer(peer.host, peer.port, invite):
                self.client.store_offline(peer.username, invite)
        return None

    def broadcast(self, content: str) -> str:
        if not self._online:
            return "Peer hiện offline do mô phỏng churn."
        peers = self.manager.all_peers()
        if not peers:
            return "Không có peer nào online để broadcast"
        message = make_msg(
            MsgType.DIRECT_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=f"[BROADCAST] {self.username}",
            to_id="ALL",
            content=content,
            timestamp=now_str(),
        )
        message = self.crypto.encrypt_content(message)
        success = sum(self.client.send_to_peer(p.host, p.port, message) for p in peers)
        failed = len(peers) - success
        result = f"Đã gửi tới {success}/{len(peers)} peer"
        if failed:
            result += f" ({failed} thất bại)"
        return result

    def get_online_peers(self):
        return self.manager.all_peers()

    def get_groups(self):
        return self.manager.all_groups()


    def send_file(
        self, target_name: str, file_path: str, conversation_type: str = "direct"
    ) -> tuple[str | None, str | None]:
        """Publish a file card; file bytes are transferred only on Download."""
        if not self._online:
            return None, "Peer hiện offline do mô phỏng churn."
        if conversation_type == "group":
            return self.file_transfer.share_group(target_name, file_path)
        return self.file_transfer.share_direct(target_name, file_path)

    def download_file(self, share_id: str, save_path: str) -> str | None:
        if not self._online:
            return "Peer hiện offline do mô phỏng churn."
        return self.file_transfer.download(share_id, save_path)

    def cancel_file(self, transfer_id: str):
        self.file_transfer.cancel(transfer_id)
