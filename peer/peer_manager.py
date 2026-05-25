"""
PeerManager – bộ nhớ trong của một peer node.
Lưu danh sách peer đang online và danh sách nhóm chat.
Thread-safe thông qua RLock.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class PeerInfo:
    peer_id:  str
    username: str
    host:     str
    port:     int
    online:   bool = True


@dataclass
class GroupInfo:
    group_id:   str
    group_name: str
    members:    list = field(default_factory=list)   # list[peer_id]


class PeerManager:
    def __init__(self):
        self._peers:  dict[str, PeerInfo]  = {}
        self._groups: dict[str, GroupInfo] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ Peers

    def set_peers(self, peer_list: list):
        """Thay thế toàn bộ danh sách peer (dùng khi nhận PEER_LIST)."""
        with self._lock:
            self._peers = {
                p["peer_id"]: PeerInfo(
                    peer_id=p["peer_id"],
                    username=p["username"],
                    host=p["host"],
                    port=p["port"],
                )
                for p in peer_list
            }

    def add_peer(self, peer_id, username, host, port):
        with self._lock:
            self._peers[peer_id] = PeerInfo(peer_id, username, host, port, online=True)

    def mark_offline(self, peer_id):
        """Đánh dấu offline nhưng GIỮ LẠI trong danh sách để store-and-forward."""
        with self._lock:
            if peer_id in self._peers:
                self._peers[peer_id].online = False

    def get_peer(self, peer_id) -> PeerInfo | None:
        with self._lock:
            return self._peers.get(peer_id)

    def get_peer_by_name(self, username: str) -> PeerInfo | None:
        """Ưu tiên peer online; nếu không có thì trả về peer offline đã biết."""
        with self._lock:
            online = [p for p in self._peers.values()
                      if p.username.lower() == username.lower() and p.online]
            if online:
                return online[0]
            offline = [p for p in self._peers.values()
                       if p.username.lower() == username.lower()]
            return offline[0] if offline else None

    def all_peers(self) -> list[PeerInfo]:
        """Chỉ trả về peer đang online."""
        with self._lock:
            return [p for p in self._peers.values() if p.online]

    # ----------------------------------------------------------------- Groups

    def add_group(self, group_id, group_name, members: list):
        with self._lock:
            self._groups[group_id] = GroupInfo(group_id, group_name, list(members))

    def get_group(self, group_id) -> GroupInfo | None:
        with self._lock:
            return self._groups.get(group_id)

    def get_group_by_name(self, name: str) -> GroupInfo | None:
        with self._lock:
            for g in self._groups.values():
                if g.group_name.lower() == name.lower():
                    return g
        return None

    def all_groups(self) -> list[GroupInfo]:
        with self._lock:
            return list(self._groups.values())

    def add_member(self, group_id, peer_id):
        with self._lock:
            g = self._groups.get(group_id)
            if g and peer_id not in g.members:
                g.members.append(peer_id)
