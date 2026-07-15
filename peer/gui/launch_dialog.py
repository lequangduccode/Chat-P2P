from __future__ import annotations

import socket

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
    QVBoxLayout,
)


class CheckMarkBox(QPushButton):
    """Consistent checkbox: white when off, blue with white tick when on."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("customCheckBox")
        self.setCheckable(True)
        self.setFixedSize(25, 25)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(self._sync_mark)
        self._sync_mark(False)

    def _sync_mark(self, checked: bool):
        self.setText("✓" if checked else "")


class CheckBoxRow(QWidget):
    toggled = Signal(bool)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("customCheckBoxRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        self.box = CheckMarkBox()
        layout.addWidget(self.box)

        self.label = QLabel(text)
        self.label.setObjectName("customCheckBoxLabel")
        self.label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.label)
        layout.addStretch(1)

        self.box.toggled.connect(self.toggled.emit)
        self.label.mousePressEvent = self._toggle_from_label

    def _toggle_from_label(self, event):
        self.box.toggle()
        event.accept()

    def isChecked(self) -> bool:
        return self.box.isChecked()

    def setChecked(self, checked: bool):
        self.box.setChecked(checked)


class LaunchDialog(QDialog):
    def __init__(self, defaults: dict | None = None, parent=None):
        super().__init__(parent)
        defaults = defaults or {}

        self.setObjectName("launchDialog")
        self.setWindowTitle("Kết nối mạng P2P")
        self.setMinimumSize(500, 500)
        self.resize(520, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)

        title = QLabel("Tham gia mạng P2P")
        title.setObjectName("launchTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Nhập thông tin peer. Ứng dụng sẽ kiểm tra tên người dùng, "
            "cổng lắng nghe và kết nối bootstrap trước khi mở cửa sổ chat."
        )
        subtitle.setObjectName("launchSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("launchCard")
        form = QFormLayout(card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Ví dụ: Alice")
        self.username_edit.setText(str(defaults.get("username", "")))
        self.username_edit.setMaxLength(32)
        form.addRow("Tên người dùng", self.username_edit)

        self.port_edit = QLineEdit()
        self.port_edit.setValidator(QIntValidator(1024, 65535, self))
        self.port_edit.setText(str(defaults.get("port", 9001)))
        self.port_edit.setPlaceholderText("9001")
        self.port_edit.setInputMethodHints(Qt.ImhDigitsOnly)
        form.addRow("Cổng peer", self.port_edit)

        self.bootstrap_host_edit = QLineEdit()
        self.bootstrap_host_edit.setText(
            str(defaults.get("bootstrap_host", "127.0.0.1"))
        )
        self.bootstrap_host_edit.setPlaceholderText("127.0.0.1")
        form.addRow("Bootstrap host", self.bootstrap_host_edit)

        self.bootstrap_port_edit = QLineEdit()
        self.bootstrap_port_edit.setValidator(QIntValidator(1, 65535, self))
        self.bootstrap_port_edit.setText(
            str(defaults.get("bootstrap_port", 9000))
        )
        self.bootstrap_port_edit.setPlaceholderText("9000")
        self.bootstrap_port_edit.setInputMethodHints(Qt.ImhDigitsOnly)
        form.addRow("Bootstrap port", self.bootstrap_port_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Khóa dùng chung giữa các peer")
        self.key_edit.setText(str(defaults.get("encryption_key", "")))
        form.addRow("Khóa mã hóa", self.key_edit)

        self.show_key = CheckBoxRow("Hiển thị khóa")
        self.show_key.toggled.connect(
            lambda checked: self.key_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        form.addRow("", self.show_key)

        root.addWidget(card)

        self.notice = QLabel(
            "Tất cả peer trong cùng mạng phải dùng cùng một khóa mã hóa."
        )
        self.notice.setObjectName("launchNotice")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)

        actions = QHBoxLayout()
        actions.addStretch(1)

        cancel = QPushButton("Thoát")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)

        self.connect_button = QPushButton("Kết nối")
        self.connect_button.setDefault(True)
        self.connect_button.clicked.connect(self._validate)
        actions.addWidget(self.connect_button)
        root.addLayout(actions)

        self.username_edit.returnPressed.connect(self._validate)
        self.key_edit.returnPressed.connect(self._validate)

    def _validate(self):
        username = self.username_edit.text().strip()
        if not username:
            QMessageBox.warning(
                self, "Thiếu tên", "Hãy nhập tên người dùng."
            )
            self.username_edit.setFocus()
            return

        if not username.replace("_", "").replace("-", "").isalnum():
            QMessageBox.warning(
                self,
                "Tên không hợp lệ",
                "Tên chỉ nên gồm chữ, số, dấu gạch dưới hoặc gạch ngang.",
            )
            self.username_edit.setFocus()
            return

        if not self.bootstrap_host_edit.text().strip():
            QMessageBox.warning(
                self, "Thiếu địa chỉ", "Hãy nhập bootstrap host."
            )
            return

        if not self.key_edit.text():
            QMessageBox.warning(
                self,
                "Thiếu khóa mã hóa",
                "Hãy nhập khóa mã hóa dùng chung cho các peer.",
            )
            self.key_edit.setFocus()
            return

        if not self.port_edit.hasAcceptableInput():
            QMessageBox.warning(
                self,
                "Cổng peer không hợp lệ",
                "Cổng peer phải là số từ 1024 đến 65535.",
            )
            self.port_edit.setFocus()
            return

        if not self.bootstrap_port_edit.hasAcceptableInput():
            QMessageBox.warning(
                self,
                "Bootstrap port không hợp lệ",
                "Bootstrap port phải là số từ 1 đến 65535.",
            )
            self.bootstrap_port_edit.setFocus()
            return

        port = int(self.port_edit.text())
        if not self._port_available(port):
            QMessageBox.critical(
                self,
                "Cổng đang được sử dụng",
                f"Cổng {port} đã được một chương trình khác sử dụng.\n"
                "Hãy chọn một cổng khác.",
            )
            self.port_edit.setFocus()
            return

        self.accept()

    @staticmethod
    def _port_available(port: int) -> bool:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def values(self) -> dict:
        return {
            "username": self.username_edit.text().strip(),
            "port": int(self.port_edit.text()),
            "bootstrap_host": self.bootstrap_host_edit.text().strip(),
            "bootstrap_port": int(self.bootstrap_port_edit.text()),
            "encryption_key": self.key_edit.text(),
        }
