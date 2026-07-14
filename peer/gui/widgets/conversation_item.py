from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class ConversationItem(QWidget):
    def __init__(self, title: str, subtitle: str = "", online=True, unread=0, is_group=False):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(11)

        avatar = QLabel("#" if is_group else title[:1].upper())
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        avatar.setStyleSheet(
            "background:#dce9ff;color:#2259b8;border-radius:20px;"
            "font-size:14px;font-weight:800;"
        )
        root.addWidget(avatar)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)
        name = QLabel(title)
        name.setStyleSheet("color:#101828;font-weight:750;font-size:14px;")
        detail = QLabel(subtitle)
        detail.setStyleSheet("color:#667085;font-size:12px;")
        detail.setTextInteractionFlags(Qt.NoTextInteraction)
        texts.addWidget(name)
        texts.addWidget(detail)
        root.addLayout(texts, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if not is_group:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{'#22b573' if online else '#98a2b3'};font-size:12px;")
            right.addWidget(dot, alignment=Qt.AlignRight)
        if unread:
            badge = QLabel(str(min(unread, 99)))
            badge.setAlignment(Qt.AlignCenter)
            badge.setMinimumSize(22, 22)
            badge.setStyleSheet(
                "background:#f04438;color:white;border-radius:11px;"
                "font-size:11px;font-weight:800;padding:0 5px;"
            )
            right.addWidget(badge, alignment=Qt.AlignRight)
        root.addLayout(right)
