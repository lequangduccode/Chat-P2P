from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from peer.gui.launch_dialog import LaunchDialog
from peer.gui.main_window import MainWindow
from peer.gui.styles import APP_STYLE
from peer.node import PeerNode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Khởi động peer P2P bằng giao diện PySide6."
    )
    parser.add_argument("--username")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument("--bootstrap-host", default="127.0.0.1")
    parser.add_argument("--bootstrap-port", type=int, default=9000)
    parser.add_argument("--encryption-key")
    parser.add_argument(
        "--no-launcher",
        action="store_true",
        help="Không mở màn hình nhập thông tin; yêu cầu đủ tham số CLI.",
    )
    return parser


def _build_node(config: dict) -> PeerNode:
    # PeerNode reads the key from the environment in the current codebase.
    os.environ["P2P_ENCRYPTION_KEY"] = config["encryption_key"]
    return PeerNode(
        username=config["username"],
        port=int(config["port"]),
        bootstrap_host=config["bootstrap_host"],
        bootstrap_port=int(config["bootstrap_port"]),
        encryption_key=config["encryption_key"],
    )


def _cli_config(args) -> dict | None:
    key = args.encryption_key or os.environ.get("P2P_ENCRYPTION_KEY", "")
    if args.username and args.port and key:
        return {
            "username": args.username,
            "host": args.host,
            "port": args.port,
            "bootstrap_host": args.bootstrap_host,
            "bootstrap_port": args.bootstrap_port,
            "encryption_key": key,
        }
    return None


def main() -> int:
    args = build_parser().parse_args()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    config = _cli_config(args)

    if args.no_launcher and config is None:
        QMessageBox.critical(
            None,
            "Thiếu tham số",
            "Khi dùng --no-launcher, bạn phải cung cấp username, port "
            "và encryption key.",
        )
        return 2

    while config is None:
        dialog = LaunchDialog(
            {
                "username": args.username or "",
                "port": args.port or 9001,
                "bootstrap_host": args.bootstrap_host,
                "bootstrap_port": args.bootstrap_port,
                "encryption_key": (
                    args.encryption_key
                    or os.environ.get("P2P_ENCRYPTION_KEY", "")
                ),
            }
        )
        if dialog.exec() != LaunchDialog.Accepted:
            return 0
        config = dialog.values()

        node = _build_node(config)
        window = MainWindow(node)

        if not node.start():
            # Registration fails both when bootstrap is unavailable and when
            # bootstrap rejects duplicate username/peer information.
            QMessageBox.critical(
                None,
                "Không thể tham gia mạng",
                "Không thể đăng ký peer.\n\n"
                "Các nguyên nhân thường gặp:\n"
                "• Bootstrap server chưa chạy.\n"
                "• Tên người dùng đã được peer khác sử dụng.\n"
                "• Cổng vừa bị chương trình khác chiếm.\n"
                "• Địa chỉ hoặc cổng bootstrap không đúng.",
            )
            try:
                node.stop()
            except Exception:
                pass
            window.deleteLater()
            config = None
            continue

        window.refresh_all()
        window.statusBar().showMessage("Đã kết nối với mạng P2P", 4000)
        window.show()
        return app.exec()

    node = _build_node(config)
    window = MainWindow(node)

    if not node.start():
        QMessageBox.critical(
            None,
            "Không thể tham gia mạng",
            "Không thể đăng ký peer. Hãy kiểm tra bootstrap, tên và cổng.",
        )
        return 1

    window.refresh_all()
    window.statusBar().showMessage("Đã kết nối với mạng P2P", 4000)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
