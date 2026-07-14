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

import os
import base64
import threading
import time
import logging

from common.protocol import MsgType, make_msg, new_id, now_str
from common.utils import get_local_ip
from common import crypto
from peer.server import PeerServer
from peer.client import PeerClient
from peer.peer_manager import PeerManager
from config import (BOOTSTRAP_HOST, BOOTSTRAP_PORT, HEARTBEAT_INTERVAL,
                    NETWORK_SECRET, DOWNLOAD_DIR, MAX_FILE_BYTES)

log = logging.getLogger(__name__)


class PeerNode:
    def __init__(
        self,
        username: str,
        port: int,
        bootstrap_host: str = BOOTSTRAP_HOST,
        bootstrap_port: int = BOOTSTRAP_PORT,
        secret: str = NETWORK_SECRET,
    ):
        self.peer_id  = new_id()
        self.username = username
        self.host     = get_local_ip()
        self.port     = port

        # Khoá mã hoá dùng chung cho cả mạng (mọi peer cùng passphrase)
        self._key = crypto.derive_key(secret)

        self.manager = PeerManager()
        self.client  = PeerClient(bootstrap_host, bootstrap_port)
        self.server  = PeerServer(self.host, self.port, self._on_message)

        self._running = False
        self._display_cb = None    # set bởi CLI

    # ------------------------------------------------------------------
    # Mã hoá / giải mã nội dung tin nhắn
    # ------------------------------------------------------------------

    def _enc(self, text: str) -> str:
        return crypto.encrypt(text, self._key)

    def _dec(self, token: str) -> str:
        pt = crypto.decrypt(token, self._key)
        return pt if pt is not None else "⚠[không giải mã được – sai khoá?]"

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
            MsgType.FILE_MSG:     self._on_file_msg,
        }
        handler = dispatch.get(t)
        if handler:
            handler(msg)

    def _on_peer_joined(self, msg):
        pid, name, host, port = (
            msg["peer_id"], msg["username"], msg["host"], msg["port"]
        )
        # Nếu peer đã biết nhưng peer_id thay đổi (reconnect sau crash),
        # chuyển pending messages sang peer_id mới
        old = self.manager.get_peer_by_name(name)
        if old and old.peer_id != pid and self.client.has_pending(old.peer_id):
            with self.client._pending_lock:
                msgs = self.client._pending.pop(old.peer_id, [])
                self.client._pending.setdefault(pid, []).extend(msgs)

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
        self.manager.mark_offline(pid)          # giữ lại để store-and-forward
        self._display(f"\n  >> {name} đã rời mạng")

    def _on_direct_msg(self, msg):
        ts      = msg.get("timestamp", "")
        sender  = msg["from_name"]
        content = self._dec(msg["content"]) if msg.get("enc") else msg["content"]
        self._display(f"\n[{ts}] {sender} → bạn: {content}")

    def _on_group_msg(self, msg):
        ts      = msg.get("timestamp", "")
        sender  = msg["from_name"]
        group   = msg["group_name"]
        content = self._dec(msg["content"]) if msg.get("enc") else msg["content"]
        self._display(f"\n[{ts}] [{group}] {sender}: {content}")

    def _on_file_msg(self, msg):
        """Nhận file: giải mã, lưu vào thư mục downloads/, thông báo."""
        sender   = msg["from_name"]
        filename = os.path.basename(msg["filename"])   # chống path traversal
        ts       = msg.get("timestamp", "")
        try:
            raw = base64.b64decode(msg["data"])
            if msg.get("enc"):
                raw = crypto.decrypt_bytes(raw, self._key)
                if raw is None:
                    self._display(f"\n  >> ⚠ File từ {sender} giải mã thất bại (sai khoá)")
                    return
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            # tránh ghi đè: thêm hậu tố nếu trùng tên
            dest = os.path.join(DOWNLOAD_DIR, filename)
            base, ext = os.path.splitext(dest)
            i = 1
            while os.path.exists(dest):
                dest = f"{base}({i}){ext}"; i += 1
            with open(dest, "wb") as f:
                f.write(raw)
            self._display(f"\n[{ts}] 📎 {sender} gửi file '{filename}' "
                          f"({len(raw)} bytes) → đã lưu: {dest}")
        except Exception as e:
            self._display(f"\n  >> ⚠ Lỗi nhận file từ {sender}: {e}")

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
            content=self._enc(content),
            enc=True,
            timestamp=now_str(),
        )

        # Nếu biết peer đang offline → lưu ngay, không cần thử gửi
        if not peer.online:
            self.client.store_offline(peer.peer_id, msg)
            return (f"'{to_username}' hiện offline. "
                    "Tin nhắn sẽ được gửi khi họ online trở lại.")

        if self.client.send_to_peer(peer.host, peer.port, msg):
            return None
        else:
            self.client.store_offline(peer.peer_id, msg)
            return (f"'{to_username}' không phản hồi. "
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
            content=self._enc(content),
            enc=True,
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

    def broadcast(self, content: str) -> str:
        """Gửi tin nhắn tới TẤT CẢ peer đang online trong mạng (flood broadcast)."""
        peers = self.manager.all_peers()
        if not peers:
            return "Không có peer nào online để broadcast"

        msg = make_msg(
            MsgType.DIRECT_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=f"[BROADCAST] {self.username}",
            to_id="ALL",
            content=self._enc(content),
            enc=True,
            timestamp=now_str(),
        )

        ok, fail = 0, 0
        for peer in peers:
            if self.client.send_to_peer(peer.host, peer.port, msg):
                ok += 1
            else:
                fail += 1

        result = f"Đã gửi tới {ok}/{len(peers)} peer"
        if fail:
            result += f" ({fail} thất bại)"
        return result

    def send_file(self, to_username: str, filepath: str) -> str | None:
        """Gửi 1 file (đã mã hoá) tới peer. Trả None nếu thành công, chuỗi lỗi nếu thất bại."""
        if not os.path.isfile(filepath):
            return f"Không tìm thấy file: {filepath}"

        size = os.path.getsize(filepath)
        if size > MAX_FILE_BYTES:
            return (f"File quá lớn ({size} bytes). Giới hạn "
                    f"{MAX_FILE_BYTES // (1024*1024)} MB/file.")

        peer = self.manager.get_peer_by_name(to_username)
        if not peer:
            return f"Không tìm thấy peer '{to_username}'"
        if not peer.online:
            return f"'{to_username}' đang offline – chưa hỗ trợ gửi file offline."

        with open(filepath, "rb") as f:
            raw = f.read()

        enc = crypto.encrypt_bytes(raw, self._key)
        msg = make_msg(
            MsgType.FILE_MSG,
            msg_id=new_id(),
            from_id=self.peer_id,
            from_name=self.username,
            filename=os.path.basename(filepath),
            size=size,
            enc=True,
            data=base64.b64encode(enc).decode("ascii"),
            timestamp=now_str(),
        )

        if self.client.send_to_peer(peer.host, peer.port, msg):
            return None
        return f"Gửi file tới '{to_username}' thất bại (peer không phản hồi)."

    # ------------------------------------------------------------------
    # Queries for CLI
    # ------------------------------------------------------------------

    def get_online_peers(self):
        return self.manager.all_peers()

    def get_groups(self):
        return self.manager.all_groups()
