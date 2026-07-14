from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class NodeBridge(QObject):
    """Converts callbacks from PeerNode worker threads into queued Qt signals."""

    direct_message = Signal(dict)
    group_message = Signal(dict)
    peer_joined = Signal(dict)
    peer_left = Signal(dict)
    group_invite = Signal(dict)
    system_notice = Signal(str)

    def __init__(self, node):
        super().__init__()
        self.node = node
        self._install_hooks()

    def _install_hooks(self):
        original_joined = self.node._on_peer_joined
        original_left = self.node._on_peer_left
        original_direct = self.node._on_direct_msg
        original_group = self.node._on_group_msg
        original_invite = self.node._on_group_invite

        def on_joined(msg):
            original_joined(msg)
            self.peer_joined.emit(dict(msg))

        def on_left(msg):
            original_left(msg)
            self.peer_left.emit(dict(msg))

        def on_direct(msg):
            original_direct(msg)
            self.direct_message.emit(dict(msg))

        def on_group(msg):
            original_group(msg)
            self.group_message.emit(dict(msg))

        def on_invite(msg):
            original_invite(msg)
            self.group_invite.emit(dict(msg))

        self.node._on_peer_joined = on_joined
        self.node._on_peer_left = on_left
        self.node._on_direct_msg = on_direct
        self.node._on_group_msg = on_group
        self.node._on_group_invite = on_invite
        self.node.set_display(self.system_notice.emit)
