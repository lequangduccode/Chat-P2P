from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)



class TickCheckBox(QCheckBox):
    """Checkbox with a consistent blue box and visible white check mark."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(24, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(2.5, 2.5, 19, 19)
        if not self.isEnabled():
            fill = QColor("#e9eef5")
            border = QColor("#d7dee8")
        elif self.isChecked():
            fill = QColor("#2f6fed")
            border = QColor("#2f6fed")
        else:
            fill = QColor("#ffffff")
            border = QColor("#b8c5d6")

        painter.setPen(QPen(border, 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 5, 5)

        if self.isChecked():
            pen = QPen(QColor("#ffffff"), 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(7, 12, 10.5, 15.5)
            painter.drawLine(10.5, 15.5, 17.5, 8.5)

        painter.end()

def _online_text(peer) -> str:
    return "Đang online" if peer.online else "Ngoại tuyến"


class PeerItemWidget(QWidget):
    """A selectable peer row with a real QCheckBox.

    The previous implementation used QListWidgetItem.checkState() while a custom
    widget covered the whole item. Qt therefore displayed an indicator that could
    not receive mouse clicks. Keeping the checkbox inside this widget fixes that
    event-delivery problem.
    """

    checkedChanged = Signal(bool)

    def __init__(
        self,
        peer,
        *,
        checked: bool = False,
        existing: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.peer = peer
        self.existing = existing
        self.setObjectName("peerDialogRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.ArrowCursor if existing else Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 7, 12, 7)
        layout.setSpacing(11)

        self.checkbox = TickCheckBox()
        self.checkbox.setObjectName("peerCheckBox")
        self.checkbox.setChecked(checked or existing)
        self.checkbox.setEnabled(not existing)
        self.checkbox.setCursor(Qt.ArrowCursor if existing else Qt.PointingHandCursor)
        self.checkbox.toggled.connect(self.checkedChanged.emit)
        layout.addWidget(self.checkbox, 0, Qt.AlignVCenter)

        avatar = QLabel(peer.username[:1].upper())
        avatar.setObjectName("dialogPeerAvatar")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(36, 36)
        avatar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(avatar)

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)

        name = QLabel(peer.username)
        name.setObjectName("dialogPeerName")
        name.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        text_box.addWidget(name)

        state = QLabel(_online_text(peer))
        state.setObjectName("dialogPeerOnline" if peer.online else "dialogPeerOffline")
        state.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        text_box.addWidget(state)
        layout.addLayout(text_box, 1)

        if existing:
            badge = QLabel("Đã trong nhóm")
            badge.setObjectName("existingMemberBadge")
            badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            layout.addWidget(badge)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.existing:
            self.checkbox.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def username(self) -> str:
        return self.peer.username


def _configure_peer_list(widget: QListWidget):
    widget.setObjectName("dialogPeerList")
    widget.setSelectionMode(QAbstractItemView.NoSelection)
    widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    widget.setSpacing(4)
    widget.setFocusPolicy(Qt.NoFocus)


def _populate_peer_list(
    widget: QListWidget,
    peers,
    *,
    checked_names=None,
    disabled_names=None,
    on_checked_changed=None,
):
    checked_names = {name.lower() for name in (checked_names or [])}
    disabled_names = {name.lower() for name in (disabled_names or [])}

    for peer in sorted(peers, key=lambda value: (not value.online, value.username.lower())):
        key = peer.username.lower()
        existing = key in disabled_names

        item = QListWidgetItem()
        item.setData(Qt.UserRole, peer.username)
        item.setSizeHint(QSize(0, 62))
        widget.addItem(item)

        row = PeerItemWidget(
            peer,
            checked=key in checked_names,
            existing=existing,
        )
        if on_checked_changed is not None:
            row.checkedChanged.connect(on_checked_changed)
        widget.setItemWidget(item, row)


def _selected_usernames(widget: QListWidget) -> list[str]:
    selected: list[str] = []
    for index in range(widget.count()):
        item = widget.item(index)
        row = widget.itemWidget(item)
        if isinstance(row, PeerItemWidget) and not row.existing and row.is_checked():
            selected.append(row.username())
    return selected


class CreateGroupDialog(QDialog):
    def __init__(self, peers, parent=None):
        super().__init__(parent)
        self.setObjectName("groupDialog")
        self.setWindowTitle("Tạo nhóm mới")
        self.setMinimumSize(500, 530)
        self.resize(540, 580)
        self._selected_members: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("Tạo cuộc trò chuyện nhóm")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        hint = QLabel("Đặt tên nhóm và chọn các peer sẽ tham gia cuộc trò chuyện.")
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form_card = QFrame()
        form_card.setObjectName("dialogCard")
        form_layout = QFormLayout(form_card)
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ví dụ: Nhóm đồ án")
        self.name_edit.textChanged.connect(self._update_accept_state)
        form_layout.addRow("Tên nhóm", self.name_edit)
        root.addWidget(form_card)

        section = QLabel("CHỌN THÀNH VIÊN")
        section.setObjectName("dialogSectionTitle")
        root.addWidget(section)

        self.members = QListWidget()
        _configure_peer_list(self.members)
        _populate_peer_list(
            self.members,
            peers,
            on_checked_changed=self._on_member_toggled,
        )
        root.addWidget(self.members, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.setObjectName("dialogActions")
        self.buttons.button(QDialogButtonBox.Ok).setText("Tạo nhóm")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Hủy")
        self.buttons.button(QDialogButtonBox.Cancel).setObjectName("secondary")
        self.buttons.accepted.connect(self._validate)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._update_accept_state()

    def _on_member_toggled(self, _checked: bool):
        # Read the current widgets immediately; this runs synchronously on click.
        self._selected_members = set(_selected_usernames(self.members))
        self._update_accept_state()

    def _update_accept_state(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(self.name_edit.text().strip()) and bool(self._selected_members)
        )

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Thiếu tên nhóm", "Hãy nhập tên nhóm.")
            return
        if not self.selected_members():
            QMessageBox.warning(self, "Chưa chọn thành viên", "Hãy chọn ít nhất một thành viên.")
            return
        self.accept()

    def selected_members(self):
        return list(self._selected_members)

    def group_name(self):
        return self.name_edit.text().strip()


class ManageGroupMembersDialog(QDialog):
    def __init__(self, group_name: str, peers, existing_member_names: set[str], parent=None):
        super().__init__(parent)
        self.setObjectName("groupDialog")
        self.setWindowTitle(f"Thêm thành viên — {group_name}")
        self.setMinimumSize(520, 500)
        self.resize(560, 550)

        self._existing = {name.lower() for name in existing_member_names}
        self._selected_members: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(13)

        title = QLabel(f"Thêm thành viên vào {group_name}")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        hint = QLabel(
            "Thành viên hiện tại được khóa để tránh chọn trùng. "
            "Bạn có thể chọn một hoặc nhiều peer mới."
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        available_count = sum(
            1 for peer in peers if peer.username.lower() not in self._existing
        )
        summary = QLabel(
            f"{len(self._existing)} thành viên hiện tại  •  "
            f"{available_count} peer có thể thêm"
        )
        summary.setObjectName("memberSummary")
        root.addWidget(summary)

        self.members = QListWidget()
        _configure_peer_list(self.members)
        _populate_peer_list(
            self.members,
            peers,
            disabled_names=existing_member_names,
            on_checked_changed=self._on_member_toggled,
        )
        root.addWidget(self.members, 1)

        empty = QLabel("Không còn peer nào để thêm vào nhóm.")
        empty.setObjectName("emptyPeerNotice")
        empty.setAlignment(Qt.AlignCenter)
        empty.setVisible(available_count == 0)
        root.addWidget(empty)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.setObjectName("dialogActions")
        self.buttons.button(QDialogButtonBox.Ok).setText("Thêm thành viên")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Hủy")
        self.buttons.button(QDialogButtonBox.Cancel).setObjectName("secondary")
        self.buttons.accepted.connect(self._validate)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._update_accept_state()

    def _on_member_toggled(self, _checked: bool):
        self._selected_members = set(_selected_usernames(self.members))
        self._update_accept_state()

    def _update_accept_state(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self._selected_members))

    def _validate(self):
        if not self.selected_members():
            QMessageBox.information(
                self,
                "Chưa chọn peer",
                "Hãy chọn ít nhất một peer mới để thêm vào nhóm.",
            )
            return
        self.accept()

    def selected_members(self):
        return list(self._selected_members)


class BroadcastDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("groupDialog")
        self.setWindowTitle("Broadcast toàn mạng")
        self.setMinimumWidth(490)
        self.resize(500, 270)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("Gửi thông báo toàn mạng")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        hint = QLabel("Tin nhắn được gửi trực tiếp tới tất cả peer đang online.")
        hint.setObjectName("dialogHint")
        root.addWidget(hint)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("Nhập nội dung broadcast...")
        root.addWidget(self.message_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.setObjectName("dialogActions")
        buttons.button(QDialogButtonBox.Ok).setText("Gửi broadcast")
        buttons.button(QDialogButtonBox.Cancel).setText("Hủy")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("secondary")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _validate(self):
        if not self.message_edit.text().strip():
            QMessageBox.warning(self, "Nội dung trống", "Hãy nhập nội dung cần gửi.")
            return
        self.accept()

    def content(self):
        return self.message_edit.text().strip()
