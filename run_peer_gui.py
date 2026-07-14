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
    )

    if not node.start():
        QMessageBox.critical(
            None,
            "Không thể kết nối",
            f"Không thể đăng ký với bootstrap server tại "
            f"{args.bootstrap_host}:{args.bootstrap_port}.",
        )
        return 1

    window = MainWindow(node)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
