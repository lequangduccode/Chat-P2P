from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from peer.churn import ChurnConfig


class ChurnDialog(QDialog):
    start_requested = Signal(object)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("churnDialog")
        self.setWindowTitle("Mô phỏng churn")
        self.setMinimumSize(560, 560)
        self.resize(590, 620)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(13)

        title = QLabel("Mô phỏng peer tham gia và rời mạng")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        hint = QLabel(
            "Peer sẽ tự unregister khỏi bootstrap, đóng cổng TCP, chuyển "
            "offline rồi đăng ký lại. Tin nhắn gửi trong lúc offline được "
            "dùng để kiểm thử store-and-forward."
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        card = QFrame()
        card.setObjectName("churnStatusCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("churnOnlineDot")
        row.addWidget(self.status_dot)

        status_box = QVBoxLayout()
        self.status_title = QLabel("Sẵn sàng")
        self.status_title.setObjectName("churnStatusTitle")
        self.status_detail = QLabel("Chưa chạy mô phỏng")
        self.status_detail.setObjectName("churnStatusDetail")
        status_box.addWidget(self.status_title)
        status_box.addWidget(self.status_detail)
        row.addLayout(status_box, 1)
        root.addWidget(card)

        settings = QFrame()
        settings.setObjectName("dialogCard")
        form = QFormLayout(settings)
        form.setContentsMargins(18, 16, 18, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.online_seconds = QSpinBox()
        self.online_seconds.setRange(1, 3600)
        self.online_seconds.setValue(10)
        self.online_seconds.setSuffix(" giây")
        form.addRow("Thời gian online", self.online_seconds)

        self.offline_seconds = QSpinBox()
        self.offline_seconds.setRange(1, 3600)
        self.offline_seconds.setValue(5)
        self.offline_seconds.setSuffix(" giây")
        form.addRow("Thời gian offline", self.offline_seconds)

        self.cycles = QSpinBox()
        self.cycles.setRange(1, 1000)
        self.cycles.setValue(3)
        self.cycles.setSuffix(" vòng")
        form.addRow("Số vòng", self.cycles)

        self.use_jitter = QCheckBox("Dùng độ lệch thời gian ngẫu nhiên")
        self.use_jitter.setObjectName("churnJitterCheck")
        form.addRow("", self.use_jitter)

        self.jitter_seconds = QSpinBox()
        self.jitter_seconds.setRange(0, 60)
        self.jitter_seconds.setValue(2)
        self.jitter_seconds.setSuffix(" giây")
        self.jitter_seconds.setEnabled(False)
        self.use_jitter.toggled.connect(self.jitter_seconds.setEnabled)
        form.addRow("Độ lệch tối đa", self.jitter_seconds)
        root.addWidget(settings)

        log_title = QLabel("NHẬT KÝ MÔ PHỎNG")
        log_title.setObjectName("dialogSectionTitle")
        root.addWidget(log_title)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("churnLog")
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)

        self.close_button = QPushButton("Đóng")
        self.close_button.setObjectName("secondary")
        self.close_button.clicked.connect(self.hide)
        actions.addWidget(self.close_button)

        self.stop_button = QPushButton("Dừng mô phỏng")
        self.stop_button.setObjectName("danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        actions.addWidget(self.stop_button)

        self.start_button = QPushButton("Bắt đầu mô phỏng")
        self.start_button.clicked.connect(self._start)
        actions.addWidget(self.start_button)
        root.addLayout(actions)

    def _start(self):
        self.start_requested.emit(ChurnConfig(
            online_seconds=self.online_seconds.value(),
            offline_seconds=self.offline_seconds.value(),
            cycles=self.cycles.value(),
            jitter_seconds=(
                self.jitter_seconds.value() if self.use_jitter.isChecked() else 0
            ),
        ))

    def set_running(self, running: bool):
        self.online_seconds.setEnabled(not running)
        self.offline_seconds.setEnabled(not running)
        self.cycles.setEnabled(not running)
        self.use_jitter.setEnabled(not running)
        self.jitter_seconds.setEnabled(
            not running and self.use_jitter.isChecked()
        )
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.close_button.setText("Ẩn" if running else "Đóng")

    def update_state(self, payload: dict):
        online = bool(payload.get("online"))
        cycle = payload.get("cycle", 0)
        total = payload.get("total_cycles", 0)
        phase = payload.get("phase", "")

        self.status_dot.setObjectName(
            "churnOnlineDot" if online else "churnOfflineDot"
        )
        self.status_dot.setStyleSheet("")
        self.status_title.setText(
            "Peer đang online" if online else "Peer đang offline"
        )

        phase_text = {
            "online_wait": "Đang chờ trước lần rời mạng tiếp theo",
            "offline_wait": "Đã unregister và đóng cổng TCP",
            "rejoined": "Đã register lại và kiểm tra tin nhắn chờ",
        }.get(phase, phase)
        self.status_detail.setText(f"Vòng {cycle}/{total} • {phase_text}")

    def append_log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {text}")

    def finish(self, result: dict):
        self.set_running(False)
        if result.get("error"):
            self.status_title.setText("Mô phỏng kết thúc có lỗi")
            self.status_detail.setText(result["error"])
        elif result.get("stopped"):
            self.status_title.setText("Đã dừng mô phỏng")
            self.status_detail.setText(
                f"Hoàn thành {result.get('completed_cycles', 0)} vòng"
            )
        else:
            self.status_title.setText("Mô phỏng hoàn tất")
            self.status_detail.setText(
                f"Hoàn thành {result.get('completed_cycles', 0)}/"
                f"{result.get('total_cycles', 0)} vòng"
            )
