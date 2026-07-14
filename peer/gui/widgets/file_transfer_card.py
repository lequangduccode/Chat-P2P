from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget
)

from peer.file_transfer.manager import human_size


class FileTransferCard(QWidget):
    cancel_requested = Signal(str)
    open_requested = Signal(str)

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setObjectName("fileTransferRow")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(22, 5, 22, 5)

        card = QFrame()
        card.setObjectName("outgoingFileCard" if message.outgoing else "incomingFileCard")
        card.setMinimumWidth(340)
        card.setMaximumWidth(500)
        body = QVBoxLayout(card)
        body.setContentsMargins(15, 13, 15, 12)
        body.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel("📄")
        icon.setObjectName("fileIcon")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignCenter)
        header.addWidget(icon)

        text_box = QVBoxLayout()
        name = QLabel(message.file_name or "File")
        name.setObjectName("fileName")
        name.setWordWrap(True)
        text_box.addWidget(name)
        size = QLabel(human_size(message.file_size))
        size.setObjectName("fileMeta")
        text_box.addWidget(size)
        header.addLayout(text_box, 1)
        body.addLayout(header)

        progress = QProgressBar()
        progress.setObjectName("fileProgress")
        progress.setTextVisible(False)
        progress.setRange(0, max(1, message.file_size))
        progress.setValue(min(message.transferred, max(1, message.file_size)))
        body.addWidget(progress)

        status_map = {
            "preparing": "Đang kiểm tra file…",
            "waiting": "Đang chờ người nhận chấp nhận…",
            "connecting": "Đang thiết lập kết nối trực tiếp…",
            "transferring": f"{human_size(message.transferred)} / {human_size(message.file_size)}",
            "completed": "Hoàn tất",
            "failed": f"Lỗi: {message.error or 'Truyền file thất bại'}",
            "rejected": f"Đã bị từ chối: {message.error or ''}",
            "cancelled": "Đã hủy",
        }
        footer = QHBoxLayout()
        status = QLabel(status_map.get(message.status, message.status))
        status.setObjectName(
            "fileStatusError" if message.status in {"failed", "rejected"} else "fileStatus"
        )
        footer.addWidget(status, 1)

        if message.status in {"preparing", "waiting", "connecting", "transferring"}:
            cancel = QPushButton("Hủy")
            cancel.setObjectName("fileCancelButton")
            cancel.clicked.connect(
                lambda: self.cancel_requested.emit(message.transfer_id)
            )
            footer.addWidget(cancel)
        elif message.status == "completed" and message.local_path:
            open_button = QPushButton("Mở file")
            open_button.setObjectName("fileOpenButton")
            open_button.clicked.connect(
                lambda: self.open_requested.emit(message.local_path)
            )
            footer.addWidget(open_button)
        body.addLayout(footer)

        if message.outgoing:
            outer.addStretch(1)
            outer.addWidget(card)
        else:
            outer.addWidget(card)
            outer.addStretch(1)
