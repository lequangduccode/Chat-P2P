from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget


class ConversationItem(QWidget):
    """Conversation row with stable columns and pixel-consistent alignment."""

    ROW_HEIGHT = 64
    AVATAR_SIZE = 40
    BADGE_SLOT_WIDTH = 30

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        online: bool = True,
        unread: int = 0,
        is_group: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("conversationRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Three fixed visual zones:
        #   avatar | name/status content | unread badge
        # The badge column always exists, even when unread == 0, so rows never shift.
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(1)
        layout.setColumnMinimumWidth(0, self.AVATAR_SIZE)
        layout.setColumnStretch(1, 1)
        layout.setColumnMinimumWidth(2, self.BADGE_SLOT_WIDTH)
        layout.setColumnStretch(2, 0)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)

        avatar = QLabel("#" if is_group else (title[:1].upper() if title else "?"))
        avatar.setObjectName("conversationAvatar")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        layout.addWidget(avatar, 0, 0, 2, 1, Qt.AlignCenter)

        name = QLabel(title)
        name.setObjectName("conversationName")
        name.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        name.setFixedHeight(21)
        layout.addWidget(name, 0, 1, 1, 1)

        status = QWidget()
        status.setObjectName("conversationStatus")
        status.setFixedHeight(20)
        status_layout = QGridLayout(status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setHorizontalSpacing(6)
        status_layout.setVerticalSpacing(0)
        status_layout.setColumnMinimumWidth(0, 9 if not is_group else 0)
        status_layout.setColumnStretch(1, 1)

        if not is_group:
            dot = QLabel("●")
            dot.setObjectName("onlineDot" if online else "offlineDot")
            dot.setAlignment(Qt.AlignCenter)
            dot.setFixedSize(9, 18)
            status_layout.addWidget(dot, 0, 0, Qt.AlignVCenter)

        detail = QLabel(subtitle)
        detail.setObjectName("conversationSubtitle")
        detail.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        detail.setTextInteractionFlags(Qt.NoTextInteraction)
        detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        detail.setFixedHeight(18)
        status_layout.addWidget(detail, 0, 1, Qt.AlignVCenter)
        layout.addWidget(status, 1, 1, 1, 1)

        # Reserve the exact same slot in every row. An empty transparent label keeps
        # geometry identical to rows that contain a red unread badge.
        badge_slot = QWidget()
        badge_slot.setObjectName("unreadBadgeSlot")
        badge_slot.setFixedSize(self.BADGE_SLOT_WIDTH, self.BADGE_SLOT_WIDTH)
        badge_layout = QGridLayout(badge_slot)
        badge_layout.setContentsMargins(0, 0, 0, 0)

        if unread > 0:
            badge = QLabel(str(min(unread, 99)))
            badge.setObjectName("unreadBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(24, 24)
            badge_layout.addWidget(badge, 0, 0, Qt.AlignCenter)
        else:
            placeholder = QLabel("")
            placeholder.setObjectName("unreadBadgePlaceholder")
            placeholder.setFixedSize(24, 24)
            badge_layout.addWidget(placeholder, 0, 0, Qt.AlignCenter)

        layout.addWidget(badge_slot, 0, 2, 2, 1, Qt.AlignCenter)
