from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget
)

from peer.file_transfer.manager import human_size


class FileTransferCard(QWidget):
    cancel_requested = Signal(str)
    open_requested = Signal(str)
    download_requested = Signal(str)

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setObjectName("fileTransferRow")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(22, 5, 22, 5)

        card = QFrame()
        card.setObjectName(
            "outgoingFileCard" if message.outgoing else "incomingFileCard"
        )
        card.setMinimumWidth(350)
        card.setMaximumWidth(510)

        body = QVBoxLayout(card)
        body.setContentsMargins(15, 13, 15, 12)
        body.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel("📄")
        icon.setObjectName("fileIcon")
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignCenter)
        header.addWidget(icon)

        text_box = QVBoxLayout()
        name = QLabel(message.file_name or "File")
        name.setObjectName("fileName")
        name.setWordWrap(True)
        text_box.addWidget(name)

        metadata = QLabel(
            f"{human_size(message.file_size)} • AES-256-GCM"
        )
        metadata.setObjectName("fileMeta")
        text_box.addWidget(metadata)
        header.addLayout(text_box, 1)
        body.addLayout(header)

        active = message.status in {"connecting", "waiting", "transferring"}
        progress = QProgressBar()
        progress.setObjectName("fileProgress")
        progress.setTextVisible(False)
        progress.setRange(0, max(1, message.file_size))
        progress.setValue(min(message.transferred, max(1, message.file_size)))
        progress.setVisible(active)
        body.addWidget(progress)

        status_map = {
            "preparing": "Đang chuẩn bị thông tin file…",
            "shared": "Đã chia sẻ • người nhận tải khi cần",
            "available": "Sẵn sàng tải xuống",
            "connecting": "Đang yêu cầu file từ người gửi…",
            "waiting": "Đang chờ kết nối dữ liệu…",
            "transferring": (
                f"{human_size(message.transferred)} / "
                f"{human_size(message.file_size)}"
            ),
            "completed": "Đã tải xuống",
            "failed": f"Lỗi: {message.error or 'Tải file thất bại'}",
            "cancelled": "Đã hủy tải",
        }

        footer = QHBoxLayout()
        status = QLabel(status_map.get(message.status, message.status))
        status.setObjectName(
            "fileStatusError" if message.status == "failed" else "fileStatus"
        )
        footer.addWidget(status, 1)

        if not message.outgoing and message.status in {
            "available", "failed", "cancelled"
        }:
            download = QPushButton("Tải xuống")
            download.setObjectName("fileDownloadButton")
            download.clicked.connect(
                lambda: self.download_requested.emit(message.transfer_id)
            )
            footer.addWidget(download)
        elif active:
            cancel = QPushButton("Hủy")
            cancel.setObjectName("fileCancelButton")
            cancel.clicked.connect(
                lambda: self.cancel_requested.emit(
                    message.request_id or message.transfer_id
                )
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
