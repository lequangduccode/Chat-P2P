from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget, QFileDialog
)

from peer.gui.bridge import NodeBridge
from peer.gui.churn_dialog import ChurnDialog
from peer.gui.dialogs import BroadcastDialog, CreateGroupDialog, ManageGroupMembersDialog
from peer.gui.group_service import add_members_to_group
from peer.gui.models import ChatMessage, Conversation, ConversationType, current_time
from peer.gui.widgets.conversation_item import ConversationItem
from peer.gui.widgets.message_bubble import MessageBubble
from peer.gui.widgets.file_transfer_card import FileTransferCard


class MainWindow(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.bridge = NodeBridge(node)
        self.conversations: dict[str, Conversation] = {}
        self.active_id: str | None = None
        self._closing = False
        # Must exist before the first refresh_all() call.
        self._refresh_in_progress = False

        self.setWindowTitle(f"P2P Chat — {node.username}")
        self.resize(1280, 800)
        self.setMinimumSize(980, 650)
        self._build_ui()
        self._connect_signals()
        self._create_shortcuts()
        self.refresh_all()

        # Only sync lightweight peer/group state periodically. Rebuilding every
        # message bubble on each timer tick made the Qt event loop stutter and
        # caused Windows to show the busy cursor.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setTimerType(Qt.CoarseTimer)
        self.refresh_timer.timeout.connect(self.refresh_peer_state)
        self.refresh_timer.start(6000)
        self.churn_dialog: ChurnDialog | None = None

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        self.setCentralWidget(splitter)

        # Left application sidebar
        sidebar = QFrame(objectName="sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(245)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 24, 20, 20)
        side.setSpacing(10)

        side.addWidget(QLabel("P2P Chat", objectName="brand"))
        side.addWidget(QLabel("Kết nối trực tiếp • TCP", objectName="mutedOnDark"))
        crypto_label = QLabel(
            f"🔒 AES-256-GCM • {self.node.crypto.fingerprint}",
            objectName="cryptoOnDark",
        )
        crypto_label.setToolTip("Key ID phải giống nhau trên tất cả peer")
        side.addWidget(crypto_label)
        side.addSpacing(22)

        self.profile_avatar = QLabel(self.node.username[:1].upper())
        self.profile_avatar.setAlignment(Qt.AlignCenter)
        self.profile_avatar.setFixedSize(64, 64)
        self.profile_avatar.setStyleSheet(
            "background:#6ea8ff;color:white;border-radius:32px;"
            "font-size:24px;font-weight:800;"
        )
        side.addWidget(self.profile_avatar, alignment=Qt.AlignHCenter)

        profile_name = QLabel(self.node.username)
        profile_name.setAlignment(Qt.AlignCenter)
        profile_name.setStyleSheet("color:white;font-weight:800;font-size:16px;")
        side.addWidget(profile_name)

        self.connection_label = QLabel(f"● Online\n{self.node.host}:{self.node.port}")
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setStyleSheet("color:#8ff0b5;font-size:12px;")
        side.addWidget(self.connection_label)
        side.addSpacing(18)

        direct_btn = QPushButton("Tin nhắn trực tiếp")
        direct_btn.clicked.connect(lambda: self.peer_list.setFocus())
        group_btn = QPushButton("Tạo nhóm")
        group_btn.setObjectName("secondary")
        group_btn.clicked.connect(self.open_create_group)
        broadcast_btn = QPushButton("Broadcast")
        broadcast_btn.setObjectName("secondary")
        broadcast_btn.clicked.connect(self.open_broadcast)

        self.churn_button = QPushButton("Mô phỏng churn")
        self.churn_button.setObjectName("secondary")
        self.churn_button.clicked.connect(self.open_churn_dialog)

        side.addWidget(direct_btn)
        side.addWidget(group_btn)
        side.addWidget(broadcast_btn)
        side.addWidget(self.churn_button)
        side.addStretch(1)

        network = QLabel("BOOTSTRAP\nRegistry + Discovery\n\nP2P CHANNEL\nDirect TCP + ACK")
        network.setStyleSheet("color:#a9c5ff;font-size:11px;")
        side.addWidget(network)
        splitter.addWidget(sidebar)

        # Conversation navigator
        navigator = QFrame(objectName="navigator")
        navigator.setMinimumWidth(290)
        navigator.setMaximumWidth(350)
        nav = QVBoxLayout(navigator)
        nav.setContentsMargins(16, 20, 16, 16)
        nav.setSpacing(8)

        nav.addWidget(QLabel("HỘI THOẠI", objectName="sectionTitle"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm peer hoặc nhóm...")
        self.search_edit.textChanged.connect(self.refresh_lists)
        nav.addWidget(self.search_edit)

        nav.addSpacing(4)
        nav.addWidget(QLabel("PEER", objectName="sectionTitle"))
        self.peer_list = QListWidget()
        self.peer_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.peer_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.peer_list.itemClicked.connect(self.select_conversation)
        nav.addWidget(self.peer_list, 3)

        nav.addSpacing(6)
        nav.addWidget(QLabel("NHÓM", objectName="sectionTitle"))
        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.group_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.group_list.itemClicked.connect(self.select_conversation)
        nav.addWidget(self.group_list, 2)
        splitter.addWidget(navigator)

        # Main chat panel
        self.chat_panel = QFrame(objectName="chatArea")
        chat = QVBoxLayout(self.chat_panel)
        chat.setContentsMargins(0, 0, 0, 0)
        chat.setSpacing(0)

        topbar = QFrame(objectName="topbar")
        topbar.setFixedHeight(86)
        top = QHBoxLayout(topbar)
        top.setContentsMargins(24, 14, 20, 14)
        top.setSpacing(10)

        titlebox = QVBoxLayout()
        titlebox.setSpacing(3)
        self.chat_title = QLabel("Chọn một cuộc trò chuyện", objectName="chatTitle")
        self.chat_subtitle = QLabel("Peer-to-peer messaging", objectName="chatSubtitle")
        titlebox.addWidget(self.chat_title)
        titlebox.addWidget(self.chat_subtitle)
        top.addLayout(titlebox)
        top.addStretch(1)

        self.manage_members_button = QPushButton("Thêm thành viên")
        self.manage_members_button.setObjectName("ghost")
        self.manage_members_button.clicked.connect(self.open_manage_members)
        self.manage_members_button.setVisible(False)
        top.addWidget(self.manage_members_button)

        self.refresh_button = QPushButton("Làm mới")
        self.refresh_button.setObjectName("secondary")
        self.refresh_button.clicked.connect(self.refresh_all)
        top.addWidget(self.refresh_button)
        chat.addWidget(topbar)

        self.message_scroll = QScrollArea(objectName="messageScroll")
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setFrameShape(QFrame.NoFrame)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_scroll.viewport().setAutoFillBackground(True)

        self.message_container = QWidget(objectName="messageCanvas")
        self.message_container.setAttribute(Qt.WA_StyledBackground, True)
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(8, 16, 8, 16)
        self.message_layout.setSpacing(1)
        self.message_layout.addStretch(1)
        self.message_scroll.setWidget(self.message_container)
        chat.addWidget(self.message_scroll, 1)

        composer = QFrame(objectName="composer")
        compose = QHBoxLayout(composer)
        compose.setContentsMargins(20, 14, 20, 16)
        compose.setSpacing(10)
        self.attach_button = QPushButton("📎")
        self.attach_button.setObjectName("attachButton")
        self.attach_button.setToolTip("Gửi file trực tiếp (tối đa 100 MB)")
        self.attach_button.setFixedSize(46, 46)
        self.attach_button.clicked.connect(self.choose_file)
        self.attach_button.setEnabled(False)
        compose.addWidget(self.attach_button)

        self.message_edit = QLineEdit()
        self.message_edit.setMinimumHeight(46)
        self.message_edit.setPlaceholderText("Nhập tin nhắn... (Enter để gửi)")
        self.message_edit.returnPressed.connect(self.send_message)
        self.message_edit.setEnabled(False)
        compose.addWidget(self.message_edit, 1)

        self.send_button = QPushButton("Gửi")
        self.send_button.setMinimumWidth(72)
        self.send_button.setMinimumHeight(46)
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setEnabled(False)
        compose.addWidget(self.send_button)
        chat.addWidget(composer)

        splitter.addWidget(self.chat_panel)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([230, 320, 730])
        self.statusBar().showMessage("Đã kết nối với mạng P2P")

    def _connect_signals(self):
        self.bridge.direct_message.connect(self.on_direct_message)
        self.bridge.group_message.connect(self.on_group_message)
        self.bridge.peer_joined.connect(lambda _: self.refresh_peer_state())
        self.bridge.peer_left.connect(lambda _: self.refresh_peer_state())
        self.bridge.group_invite.connect(lambda _: self.refresh_peer_state(update_header=True))
        self.bridge.system_notice.connect(self.on_system_notice)
        self.bridge.file_offer.connect(self.on_file_offer)
        self.bridge.file_progress.connect(self.on_file_progress)
        self.bridge.file_completed.connect(self.on_file_completed)
        self.bridge.file_failed.connect(self.on_file_failed)
        self.bridge.file_rejected.connect(self.on_file_rejected)
        self.bridge.churn_state.connect(self.on_churn_state)
        self.bridge.churn_log.connect(self.on_churn_log)
        self.bridge.churn_finished.connect(self.on_churn_finished)

    def _create_shortcuts(self):
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence.Refresh)
        refresh.triggered.connect(self.refresh_all)
        self.addAction(refresh)

    def refresh_all(self):
        """Manual full refresh. Rendering is performed only on explicit request."""
        self.refresh_peer_state(update_header=True)
        if self.active_id:
            self.render_active_conversation()

    def refresh_peer_state(self, update_header: bool = True):
        """Synchronize local manager state without recreating the chat history."""
        if self._refresh_in_progress or self._closing:
            return
        self._refresh_in_progress = True
        try:
            self._sync_conversations()
            self.refresh_lists()
            if update_header and self.active_id in self.conversations:
                conv = self.conversations[self.active_id]
                self.chat_title.setText(conv.title)
                self.chat_subtitle.setText(conv.subtitle)
        finally:
            self._refresh_in_progress = False

    def _sync_conversations(self):
        manager = self.node.manager
        with manager._lock:
            known_peers = list(manager._peers.values())
        for peer in known_peers:
            cid = f"direct:{peer.username.lower()}"
            conv = self.conversations.get(cid)
            if conv is None:
                conv = Conversation(cid, peer.username, ConversationType.DIRECT)
                self.conversations[cid] = conv
            conv.title = peer.username
            conv.online = peer.online
            conv.subtitle = "Online" if peer.online else "Offline • tin nhắn sẽ được lưu"

        for group in self.node.manager.all_groups():
            cid = f"group:{group.group_name.lower()}"
            conv = self.conversations.get(cid)
            if conv is None:
                conv = Conversation(cid, group.group_name, ConversationType.GROUP)
                self.conversations[cid] = conv
            conv.title = group.group_name
            conv.online = True
            conv.subtitle = f"{len(group.members)} thành viên"

    def refresh_lists(self):
        selected = self.active_id
        query = self.search_edit.text().strip().lower()
        self.peer_list.clear()
        self.group_list.clear()

        direct = [c for c in self.conversations.values() if c.conversation_type == ConversationType.DIRECT]
        groups = [c for c in self.conversations.values() if c.conversation_type == ConversationType.GROUP]
        ordered = sorted(direct, key=lambda c: (not c.online, c.title.lower())) + sorted(groups, key=lambda c: c.title.lower())

        for conv in ordered:
            if query and query not in conv.title.lower():
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, conv.conversation_id)
            widget = ConversationItem(
                conv.title, conv.subtitle, conv.online, conv.unread,
                is_group=conv.conversation_type == ConversationType.GROUP,
            )
            item.setSizeHint(widget.sizeHint())
            target = self.group_list if conv.conversation_type == ConversationType.GROUP else self.peer_list
            target.addItem(item)
            target.setItemWidget(item, widget)
            if conv.conversation_id == selected:
                target.setCurrentItem(item)

    def select_conversation(self, item):
        cid = item.data(Qt.UserRole)
        self.active_id = cid
        self.conversations[cid].unread = 0
        self.refresh_lists()
        self.render_active_conversation()
        self.message_edit.setFocus()

    def render_active_conversation(self):
        if not self.active_id or self.active_id not in self.conversations:
            return
        conv = self.conversations[self.active_id]
        self.chat_title.setText(conv.title)
        self.chat_subtitle.setText(conv.subtitle)
        self.manage_members_button.setVisible(conv.conversation_type == ConversationType.GROUP)
        self.message_edit.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(
            self.node.is_online
            and (
                conv.conversation_type == ConversationType.GROUP
                or (
                    conv.conversation_type == ConversationType.DIRECT
                    and conv.online
                )
            )
        )

        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for msg in conv.messages:
            if msg.kind == "file":
                widget = FileTransferCard(msg)
                widget.cancel_requested.connect(self.node.cancel_file)
                widget.open_requested.connect(self.open_local_file)
                widget.download_requested.connect(self.download_shared_file)
            else:
                widget = MessageBubble(
                    msg.sender, msg.content, msg.timestamp, msg.outgoing, msg.status
                )
            self.message_layout.insertWidget(
                self.message_layout.count() - 1,
                widget,
            )
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def send_message(self):
        content = self.message_edit.text().strip()
        if not content or not self.active_id:
            return
        conv = self.conversations[self.active_id]
        if conv.conversation_type == ConversationType.DIRECT:
            error = self.node.send_direct(conv.title, content)
        elif conv.conversation_type == ConversationType.GROUP:
            error = self.node.send_group(conv.title, content)
        else:
            error = "Loại hội thoại không hợp lệ"

        status = "queued" if error else "sent"
        conv.messages.append(ChatMessage(
            conv.conversation_id, conv.conversation_type, self.node.username,
            content, current_time(), outgoing=True, status=status,
        ))
        self.message_edit.clear()
        self.render_active_conversation()
        self.statusBar().showMessage(error or "Đã gửi tin nhắn", 7000 if error else 2500)

    def on_direct_message(self, msg: dict):
        sender = msg.get("from_name", "Unknown")
        is_broadcast = sender.startswith("[BROADCAST]")
        display_sender = sender.replace("[BROADCAST]", "").strip() if is_broadcast else sender
        cid = f"direct:{display_sender.lower()}"
        conv = self.conversations.get(cid)
        if conv is None:
            conv = Conversation(cid, display_sender, ConversationType.DIRECT, "Tin nhắn mới")
            self.conversations[cid] = conv
        prefix = "📣 " if is_broadcast else ""
        conv.messages.append(ChatMessage(
            cid, ConversationType.DIRECT, sender,
            prefix + msg.get("content", ""), msg.get("timestamp", current_time()),
        ))
        if self.active_id != cid:
            conv.unread += 1
        self.refresh_lists()
        if self.active_id == cid:
            self.render_active_conversation()
        self.statusBar().showMessage(f"Tin nhắn mới từ {sender}", 4000)

    def on_group_message(self, msg: dict):
        name = msg.get("group_name", "Nhóm")
        cid = f"group:{name.lower()}"
        conv = self.conversations.get(cid)
        if conv is None:
            conv = Conversation(cid, name, ConversationType.GROUP, "Nhóm chat")
            self.conversations[cid] = conv
        conv.messages.append(ChatMessage(
            cid, ConversationType.GROUP, msg.get("from_name", "Unknown"),
            msg.get("content", ""), msg.get("timestamp", current_time()),
        ))
        if self.active_id != cid:
            conv.unread += 1
        self.refresh_lists()
        if self.active_id == cid:
            self.render_active_conversation()
        self.statusBar().showMessage(f"Tin nhắn mới trong nhóm {name}", 4000)


    def open_churn_dialog(self):
        if self.churn_dialog is None:
            self.churn_dialog = ChurnDialog(self)
            self.churn_dialog.start_requested.connect(self.start_churn)
            self.churn_dialog.stop_requested.connect(self.stop_churn)
        self.churn_dialog.set_running(self.node.churn.running)
        self.churn_dialog.show()
        self.churn_dialog.raise_()
        self.churn_dialog.activateWindow()

    def start_churn(self, config):
        error = self.node.churn.start(config)
        if error:
            QMessageBox.warning(self, "Không thể chạy churn", error)
            return
        if self.churn_dialog:
            self.churn_dialog.set_running(True)
            self.churn_dialog.append_log("Đã bắt đầu mô phỏng.")
        self.churn_button.setText("Churn đang chạy…")
        self.churn_button.setEnabled(False)
        self.statusBar().showMessage("Mô phỏng churn đã bắt đầu", 5000)

    def stop_churn(self):
        self.node.churn.stop(reconnect=True)
        if self.churn_dialog:
            self.churn_dialog.append_log(
                "Đang dừng và khôi phục peer về online…"
            )
            self.churn_dialog.stop_button.setEnabled(False)

    def on_churn_state(self, payload: dict):
        online = bool(payload.get("online"))
        cycle = payload.get("cycle", 0)
        total = payload.get("total_cycles", 0)

        if online:
            self.connection_label.setText(
                f"● Online\n{self.node.host}:{self.node.port}"
            )
            self.connection_label.setStyleSheet(
                "color:#8ff0b5;font-size:12px;"
            )
        else:
            self.connection_label.setText(
                f"● Offline — churn\n{self.node.host}:{self.node.port}"
            )
            self.connection_label.setStyleSheet(
                "color:#ffb4ab;font-size:12px;"
            )

        enabled = online and self.active_id is not None
        self.message_edit.setEnabled(enabled)
        self.send_button.setEnabled(enabled)

        conv = self.conversations.get(self.active_id) if self.active_id else None
        self.attach_button.setEnabled(bool(
            online
            and conv
            and (
                conv.conversation_type == ConversationType.GROUP
                or (
                    conv.conversation_type == ConversationType.DIRECT
                    and conv.online
                )
            )
        ))

        if self.churn_dialog:
            self.churn_dialog.update_state(payload)

        state = "online" if online else "offline"
        self.statusBar().showMessage(
            f"Churn vòng {cycle}/{total}: peer {state}", 4000
        )
        self.refresh_lists()

    def on_churn_log(self, text: str):
        if self.churn_dialog:
            self.churn_dialog.append_log(text)

    def on_churn_finished(self, result: dict):
        self.churn_button.setText("Mô phỏng churn")
        self.churn_button.setEnabled(True)

        if self.churn_dialog:
            self.churn_dialog.finish(result)

        if self.node.is_online:
            self.connection_label.setText(
                f"● Online\n{self.node.host}:{self.node.port}"
            )
            self.connection_label.setStyleSheet(
                "color:#8ff0b5;font-size:12px;"
            )
            self.refresh_all()

        if result.get("error"):
            self.statusBar().showMessage(
                f"Churn lỗi: {result['error']}", 8000
            )
        elif result.get("stopped"):
            self.statusBar().showMessage("Đã dừng mô phỏng churn", 5000)
        else:
            self.statusBar().showMessage(
                f"Hoàn thành {result.get('completed_cycles', 0)} vòng churn",
                6000,
            )

    def choose_file(self):
        if not self.active_id:
            return
        conv = self.conversations.get(self.active_id)
        if not conv:
            return
        if conv.conversation_type == ConversationType.DIRECT and not conv.online:
            QMessageBox.warning(
                self,
                "Peer offline",
                "Có thể gửi metadata qua hàng đợi, nhưng người nhận chỉ tải được "
                "khi bạn và họ cùng online. Hãy thử lại khi peer online.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file để chia sẻ"
        )
        if not file_path:
            return

        share_id, error = self.node.send_file(
            conv.title,
            file_path,
            conv.conversation_type.value,
        )
        if error:
            QMessageBox.warning(self, "Không thể chia sẻ file", error)
            return

        path = Path(file_path)
        conv.messages.append(ChatMessage(
            conv.conversation_id,
            conv.conversation_type,
            self.node.username,
            "",
            current_time(),
            outgoing=True,
            status="preparing",
            kind="file",
            transfer_id=share_id or "",
            file_name=path.name,
            file_size=path.stat().st_size,
            local_path=str(path),
        ))
        self.render_active_conversation()
        self.statusBar().showMessage(
            "Đang tính SHA-256 và đăng file vào cuộc trò chuyện…", 5000
        )

    def on_file_offer(self, offer: dict):
        sender = offer.get("from_name", "Unknown")
        filename = offer.get("filename", "file")
        size = int(offer.get("size", 0))
        share_id = offer.get("share_id") or offer.get("transfer_id", "")
        conversation_type = offer.get("conversation_type", "direct")

        if conversation_type == "group":
            group_name = offer.get("group_name") or offer.get("target_name", "Nhóm")
            cid = f"group:{group_name.lower()}"
            conv_type = ConversationType.GROUP
            conv = self.conversations.get(cid)
            if conv is None:
                conv = Conversation(
                    cid, group_name, ConversationType.GROUP, "Nhóm chat"
                )
                self.conversations[cid] = conv
        else:
            cid = f"direct:{sender.lower()}"
            conv_type = ConversationType.DIRECT
            conv = self.conversations.get(cid)
            if conv is None:
                conv = Conversation(
                    cid, sender, ConversationType.DIRECT, "Có file mới"
                )
                self.conversations[cid] = conv

        # Avoid duplicate card when a persisted FILE_SHARE is delivered twice.
        for existing in conv.messages:
            if existing.kind == "file" and existing.transfer_id == share_id:
                return

        conv.messages.append(ChatMessage(
            cid,
            conv_type,
            sender,
            "",
            offer.get("timestamp", current_time()),
            outgoing=False,
            status="available",
            kind="file",
            transfer_id=share_id,
            file_name=filename,
            file_size=size,
        ))
        if self.active_id != cid:
            conv.unread += 1
        self.refresh_lists()
        if self.active_id == cid:
            self.render_active_conversation()
        self.statusBar().showMessage(
            f"{sender} đã chia sẻ file {filename}", 5000
        )

    def download_shared_file(self, share_id: str):
        conv, message = self._find_transfer_message(share_id)
        if not message:
            return

        default_path = str(Path.home() / "Downloads" / message.file_name)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Chọn nơi lưu file",
            default_path,
        )
        if not save_path:
            return

        error = self.node.download_file(share_id, save_path)
        if error:
            QMessageBox.warning(self, "Không thể tải file", error)
            return

        message.status = "connecting"
        message.local_path = save_path
        message.error = ""
        if self.active_id == conv.conversation_id:
            self.render_active_conversation()
        self.statusBar().showMessage(
            f"Đang yêu cầu tải {message.file_name}…", 5000
        )
    def _find_transfer_message(self, transfer_id: str):
        for conv in self.conversations.values():
            for message in conv.messages:
                if (
                    message.kind == "file"
                    and (
                        message.transfer_id == transfer_id
                        or message.request_id == transfer_id
                    )
                ):
                    return conv, message
        return None, None

    def on_file_progress(self, payload: dict):
        conv, message = self._find_transfer_message(payload.get("transfer_id", ""))
        if not message:
            return
        message.status = payload.get("status", message.status)
        message.request_id = payload.get("request_id", message.request_id)
        message.transferred = int(
            payload.get("transferred", message.transferred)
        )
        message.local_path = payload.get("local_path", message.local_path)
        if self.active_id == conv.conversation_id:
            self.render_active_conversation()
        percent = int(100 * message.transferred / max(1, message.file_size))
        self.statusBar().showMessage(
            f"{message.file_name}: {percent}% — {message.status}", 2500
        )

    def on_file_completed(self, payload: dict):
        conv, message = self._find_transfer_message(payload.get("transfer_id", ""))
        if not message:
            return
        direction = payload.get("direction", "")
        if direction == "outgoing" and payload.get("status") == "shared":
            message.status = "shared"
            message.transferred = 0
            self.statusBar().showMessage(
                f"Đã chia sẻ file: {message.file_name}", 6000
            )
        else:
            message.status = "completed"
            message.transferred = message.file_size
            message.request_id = payload.get("request_id", message.request_id)
            message.local_path = payload.get("local_path", message.local_path)
            self.statusBar().showMessage(
                f"Đã tải xong: {message.file_name}", 6000
            )
        if self.active_id == conv.conversation_id:
            self.render_active_conversation()

    def on_file_failed(self, payload: dict):
        conv, message = self._find_transfer_message(payload.get("transfer_id", ""))
        if not message:
            return
        message.status = payload.get("status", "failed")
        if message.status != "cancelled":
            message.status = "failed"
        message.error = payload.get("error", "Truyền file thất bại")
        if self.active_id == conv.conversation_id:
            self.render_active_conversation()
        self.statusBar().showMessage(message.error, 7000)

    def on_file_rejected(self, payload: dict):
        payload = dict(payload)
        payload["status"] = "failed"
        payload["error"] = payload.get("reason", "Không thể tải file")
        self.on_file_failed(payload)

    def open_local_file(self, path: str):
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def _human_size(size: int) -> str:
        from peer.file_transfer.manager import human_size
        return human_size(size)

    def on_system_notice(self, text: str):
        clean = " ".join(text.split())
        if clean:
            self.statusBar().showMessage(clean, 5000)

    def open_create_group(self):
        peers = self._known_peers()
        if not peers:
            QMessageBox.information(self, "Không có peer", "Chưa có peer nào trong danh sách.")
            return
        dialog = CreateGroupDialog(peers, self)
        if dialog.exec():
            error = self.node.create_group(dialog.group_name(), dialog.selected_members())
            if error:
                QMessageBox.warning(self, "Không thể tạo nhóm", error)
                return
            self.refresh_all()
            self.active_id = f"group:{dialog.group_name().lower()}"
            self.refresh_lists()
            self.render_active_conversation()
            self.statusBar().showMessage(f"Đã tạo nhóm {dialog.group_name()}", 4000)

    def open_manage_members(self):
        if not self.active_id:
            return
        conv = self.conversations.get(self.active_id)
        if not conv or conv.conversation_type != ConversationType.GROUP:
            return
        group = self.node.manager.get_group_by_name(conv.title)
        if not group:
            QMessageBox.warning(self, "Không tìm thấy nhóm", "Dữ liệu nhóm không còn tồn tại.")
            return

        existing_names = {self.node.username.lower()}
        for member_id in group.members:
            if member_id == self.node.peer_id:
                continue
            peer = self.node.manager.get_peer(member_id)
            if peer:
                existing_names.add(peer.username.lower())

        candidates = self._known_peers()
        available = [p for p in candidates if p.username.lower() not in existing_names]
        if not available:
            QMessageBox.information(self, "Không còn peer", "Tất cả peer đã biết đều đang ở trong nhóm.")
            return

        dialog = ManageGroupMembersDialog(conv.title, candidates, existing_names, self)
        if dialog.exec():
            result = add_members_to_group(self.node, conv.title, dialog.selected_members())
            if result and not result.startswith("Đã thêm thành viên"):
                QMessageBox.warning(self, "Không thể thêm thành viên", result)
                return
            self.refresh_all()
            message = result or "Đã thêm thành viên và đồng bộ danh sách nhóm."
            QMessageBox.information(self, "Cập nhật nhóm", message)
            self.statusBar().showMessage(message, 5000)

    def _known_peers(self):
        with self.node.manager._lock:
            return list(self.node.manager._peers.values())

    def open_broadcast(self):
        dialog = BroadcastDialog(self)
        if dialog.exec():
            result = self.node.broadcast(dialog.content())
            QMessageBox.information(self, "Kết quả broadcast", result)
            self.statusBar().showMessage(result, 5000)

    def closeEvent(self, event: QCloseEvent):
        if self._closing:
            event.accept()
            return
        self._closing = True
        self.refresh_timer.stop()
        try:
            self.node.stop()
        finally:
            event.accept()
