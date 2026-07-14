from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MessageBubble(QWidget):
    """A responsive chat bubble for incoming and outgoing messages."""

    MIN_BUBBLE_WIDTH = 150
    MAX_BUBBLE_WIDTH = 560

    def __init__(
        self,
        sender: str,
        content: str,
        timestamp: str,
        outgoing: bool = False,
        status: str = "sent",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("messageRow")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(22, 5, 22, 5)
        outer.setSpacing(10)

        bubble = QFrame()
        bubble.setObjectName("outgoingBubble" if outgoing else "incomingBubble")
        bubble.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

        body = QVBoxLayout(bubble)
        body.setContentsMargins(14, 10, 14, 9)
        body.setSpacing(5)

        if not outgoing:
            author = QLabel(sender)
            author.setObjectName("messageAuthor")
            author.setTextInteractionFlags(Qt.TextSelectableByMouse)
            author.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            body.addWidget(author)

        text = QLabel(content)
        text.setObjectName("outgoingMessageText" if outgoing else "incomingMessageText")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        body.addWidget(text)

        status_icon = {
            "sent": "✓",
            "delivered": "✓✓",
            "pending": "◷",
            "failed": "!",
        }.get(status, "✓")

        meta = QLabel(f"{timestamp}  {status_icon}")
        meta.setObjectName("outgoingMessageMeta" if outgoing else "incomingMessageMeta")
        meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        body.addWidget(meta)

        bubble_width = self._preferred_width(sender, content, outgoing)
        bubble.setFixedWidth(bubble_width)

        if outgoing:
            outer.addStretch(1)
            outer.addWidget(bubble, 0, Qt.AlignRight | Qt.AlignTop)
        else:
            outer.addWidget(bubble, 0, Qt.AlignLeft | Qt.AlignTop)
            outer.addStretch(1)

    def _preferred_width(self, sender: str, content: str, outgoing: bool) -> int:
        """Estimate a readable width without producing tiny stacked labels."""
        metrics = QFontMetrics(self.font())
        lines = content.splitlines() or [content]
        widest_text = max((metrics.horizontalAdvance(line) for line in lines), default=0)

        if not outgoing:
            widest_text = max(widest_text, metrics.horizontalAdvance(sender))

        # Horizontal content margins plus a little room for the metadata line.
        estimated = max(widest_text + 42, metrics.horizontalAdvance("00:00:00  ✓✓") + 42)

        # Long messages should wrap rather than create an excessively wide bubble.
        if len(content) > 52 or any(len(line) > 52 for line in lines):
            estimated = self.MAX_BUBBLE_WIDTH

        return max(self.MIN_BUBBLE_WIDTH, min(self.MAX_BUBBLE_WIDTH, estimated))
