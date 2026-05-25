"""
PeerNode – bộ điều phối trung tâm của một peer.

Kết hợp:
  - PeerServer  (nhận kết nối đến)
  - PeerClient  (gửi tin, giao tiếp bootstrap)
  - PeerManager (bộ nhớ: danh sách peer, nhóm)

Giao diện công khai (dùng bởi CLI):
  start() / stop()
  send_direct(to_username, content)  -> error_str | None
  send_group(group_name, content)    -> error_str | None
  create_group(group_name, [names])  -> error_str | None
  get_online_peers()                 -> list[PeerInfo]
  get_groups()                       -> list[GroupInfo]
"""

import threading
import time
import logging

from common.protocol import MsgType, make_msg, new_id, now_str
from common.utils import get_local_ip
from peer.server import PeerServer
from peer.client import PeerClient
from peer.peer_manager import PeerManager
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, HEARTBEAT_INTERVAL

log = logging.getLogger(__name__)


class PeerNode:
    def __init__(
        self,
        username: str,
        port: int,
        bootstrap_host: str = BOOTSTRAP_HOST,
        bootstrap_port: int = BOOTSTRAP_PORT,
    ):
        self.peer_id  = new_id()
        self.username = username
        self.host     = get_local_ip()
        self.port     = port

        self.manager = PeerManager()
        self.client  = PeerClient(bootstrap_host, bootstrap_port)
        self.server  = PeerServer(self.host, self.port, self._on_message)

        self._running = False
        self._display_cb = None    # set bởi CLI

    # ------------------------------------------------------------------
    # Display helper
    # ------------------------------------------------------------------

    def set_display(self, callback):
        """CLI đăng ký hàm hiển thị tin nhắn đến."""
        self._display_cb = callback

    def _display(self, text: str):
        if self._display_cb:
            self._display_cb(text)
        else:
            print(text)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Khởi động server, đăng ký với bootstrap. Trả về False nếu thất bại."""
        self.server.start()

        if not self.client.register(
            self.peer_id, self.username, self.host, self.port
        ):
            print(f"[!] Không thể kết nối Bootstrap tại "
                  f"{BOOTSTRAP_HOST}:{BOOTSTRAP_PORT}")
            return False

        # Lấy danh sách peer ban đầu
        self._refresh_peers()
        self._running = True

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._refresh_loop,   daemon=True).start()

        log.info(f"Peer '{self.username}' sẵn sàng  "
                 f"(id={self.peer_id[:8]}…, {self.host}:{self.port})")
        return True

    def stop(self):
        self._running = False
        self.client.unregister(self.peer_id)
        self.server.stop()

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            if self._running:
                ok = self.client.heartbeat(self.peer_id)
                if not ok:
                    log.warning("Heartbeat thất bại")

    def _refresh_loop(self):
        """Cập nhật danh sách peer mỗi 30 giây (dự phòng cho push)."""
        while self._running:
            time.sleep(30)
            if self._running:
                self._refresh_peers()

    def _refresh_peers(self):
        peers = self.client.get_peers(self.peer_id)
        self.manager.set_peers(peers)

    # ------------------------------------------------------------------
    # Incoming message dispatcher
    # ------------------------------------------------------------------

    def _on_message(self, msg: dict):
        t = msg.get("type")
        dispatch = {
            MsgType.PEER_JOINED:  self._on_peer_joined,
            MsgType.PEER_LEFT:    self._on_peer_left,
            MsgType.DIRECT_MSG:   self._on_direct_msg,
            MsgType.GROUP_MSG:    self._on_group_msg,
            MsgType.GROUP_INVITE: self._on_group_invite,
        }
        handler = dispatch.get(t)
        if handler:
            handler(msg)

    def _on_peer_joined(self, msg):
        pid, name, host, port = (
            msg["peer_id"], msg["username"], msg["host"], msg["port"]
        )
        self.manager.add_peer(pid, name, host, port)
        self._display(f"\n  >> {name} vừa tham gia mạng")

        # Store-and-forward: flush pending messages
        if self.client.has_pending(pid):
            sent = self.client.flush_pending(pid, host, port)
            if sent:
                self._display(
                    f"  >> Đã gửi {sent} tin nhắn đang chờ tới {name}"
                )

    def _on_peer_left(self, msg):
        pid, name = msg["peer_id"], msg["username"]
        self.manager.remove_peer(pid)
        self._display(f"\n  >> {name} đã rời mạng")

    def _on_direct_msg(self, msg):
        ts      = msg.get("timestamp", "")
        sender  = msg["from_name"]
        content = msg["content"]
        self._display(f"\n[{ts}] {sender} → bạn: {content}")

    def _on_group_msg(self, msg):
        ts      = msg.get("timestamp", "")
        sender  = msg["from_name"]
        group   = msg["group_name"]
        content = msg["content"]
        self._display(f"\n[{ts}] [{group}] {sender}: {content}")

    def _on_group_invite(self, msg):
        from_name  = msg["from_name"]
        group_id   = msg["group_id"]
        group_name = msg["group_name"]
        members    = msg["members"]
        self.manager.add_group(group_id, group_name, members)
        self._display(
            f"\n  >> {from_name} đã thêm bạn vào nhóm '{group_name}' "
            f"({len(members)} thành viên)"
        )

    # ------------------------------------------------------------------
    # Public actions (called by CLI)
    # ------------------------------------------------------------------

    def send_direct(self, to_username: str, content: str) -> str | None:
        """Gửi tin nhắn trực tiếp. Trả về None nếu thành công, chuỗi lỗi nếu thất bại."""
        peer = self.manager.get_peer_by_name(to_username)
        if not peer:
            return f"Không tìm thấy peer '{to_username}'"

        msg = make_msg(
            MsgType.DIRECT_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=self.username,
            to_id=peer.peer_id,
            content=content,
            timestamp=now_str(),
        )

        if self.client.send_to_peer(peer.host, peer.port, msg):
            return None
        else:
            self.client.store_offline(peer.peer_id, msg)
            return (f"'{to_username}' hiện offline. "
                    "Tin nhắn sẽ được gửi khi họ online trở lại.")

    def send_group(self, group_name: str, content: str) -> str | None:
        group = self.manager.get_group_by_name(group_name)
        if not group:
            return f"Không tìm thấy nhóm '{group_name}'"

        msg = make_msg(
            MsgType.GROUP_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=self.username,
            group_id=group.group_id,
            group_name=group.group_name,
            content=content,
            timestamp=now_str(),
        )

        offline = []
        for member_id in group.members:
            if member_id == self.peer_id:
                continue
            peer = self.manager.get_peer(member_id)
            if peer:
                if not self.client.send_to_peer(peer.host, peer.port, msg):
                    self.client.store_offline(member_id, msg)
                    offline.append(peer.username)
            else:
                self.client.store_offline(member_id, msg)

        if offline:
            return f"Một số thành viên offline, tin nhắn đã lưu: {', '.join(offline)}"
        return None

    def create_group(self, group_name: str, member_names: list) -> str | None:
        group_id = new_id()
        members  = [self.peer_id]
        not_found = []

        for name in member_names:
            peer = self.manager.get_peer_by_name(name)
            if peer:
                members.append(peer.peer_id)
            else:
                not_found.append(name)

        if not_found:
            return f"Không tìm thấy peer: {', '.join(not_found)}"

        self.manager.add_group(group_id, group_name, members)

        invite = make_msg(
            MsgType.GROUP_INVITE,
            from_id=self.peer_id,
            from_name=self.username,
            group_id=group_id,
            group_name=group_name,
            members=members,
        )

        for pid in members:
            if pid == self.peer_id:
                continue
            peer = self.manager.get_peer(pid)
            if peer:
                self.client.send_to_peer(peer.host, peer.port, invite)

        return None

    # ------------------------------------------------------------------
    # Queries for CLI
    # ------------------------------------------------------------------

    def get_online_peers(self):
        return self.manager.all_peers()

    def get_groups(self):
        return self.manager.all_groups()
