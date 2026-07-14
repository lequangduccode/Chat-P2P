#!/usr/bin/env python3
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, DEFAULT_PEER_PORT
from peer.node import PeerNode
from peer.gui.main_window import MainWindow
from peer.gui.styles import APP_STYLE


def parse_args():
    parser = argparse.ArgumentParser(description="P2P Chat - PySide6 GUI")
    parser.add_argument("--username", "-u", required=True)
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PEER_PORT)
    parser.add_argument("--bootstrap-host", default=BOOTSTRAP_HOST)
    parser.add_argument("--bootstrap-port", type=int, default=BOOTSTRAP_PORT)
    parser.add_argument(
        "--encryption-key",
        default=os.environ.get("P2P_ENCRYPTION_KEY", "p2p-chat-demo-2026"),
        help=("Khóa dùng chung cho AES-256-GCM. Tất cả peer phải dùng cùng khóa; "
              "có thể đặt bằng biến môi trường P2P_ENCRYPTION_KEY."),
    )
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="[%(name)s] %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("P2P Chat")
    app.setStyleSheet(APP_STYLE)

    node = PeerNode(
        username=args.username,
        port=args.port,
        bootstrap_host=args.bootstrap_host,
        bootstrap_port=args.bootstrap_port,
        encryption_key=args.encryption_key,
    )

    # Create MainWindow before node.start(). MainWindow installs NodeBridge,
    # which must already be listening when bootstrap registration triggers
    # store-and-forward delivery. Otherwise queued messages arrive only at the
    # backend callback and are printed to the terminal before the GUI exists.
    window = MainWindow(node)

    if not node.start():
        QMessageBox.critical(
            window,
            "Không thể kết nối",
            f"Không thể đăng ký với bootstrap server tại "
            f"{args.bootstrap_host}:{args.bootstrap_port}.",
        )
        window.close()
        return 1

    # Synchronize peers/groups learned during registration, then show the UI.
    window.refresh_all()
    window.statusBar().showMessage(
        f"Đã kết nối • Mã hóa AES-256-GCM • Key ID {node.crypto.fingerprint}",
        8000,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
