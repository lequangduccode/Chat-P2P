#!/usr/bin/env python3
"""
Khởi động Peer Node với GIAO DIỆN ĐỒ HOẠ (Tkinter).

Dùng:
    python run_gui.py
    python run_gui.py -u Alice -p 9001
    python run_gui.py -u Bob -p 9002 --bootstrap-host 192.168.1.10

Nếu không truyền -u/-p thì có thể nhập trực tiếp trên màn hình đăng nhập.
Chỉ dùng thư viện chuẩn của Python (tkinter) – không cần cài thêm.
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.WARNING, format="[%(name)s] %(message)s")

try:
    import tkinter  # noqa: F401
except ImportError:
    print("[!] Máy này thiếu Tkinter. Cài đặt Python bản đầy đủ (có 'tcl/tk').")
    sys.exit(1)

from peer.gui import ChatGUI
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, DEFAULT_PEER_PORT


def main():
    parser = argparse.ArgumentParser(description="P2P Chat – GUI Peer Node")
    parser.add_argument("--username", "-u", default="")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PEER_PORT)
    parser.add_argument("--bootstrap-host", default=BOOTSTRAP_HOST)
    parser.add_argument("--bootstrap-port", type=int, default=BOOTSTRAP_PORT)
    args = parser.parse_args()

    gui = ChatGUI()
    # Điền sẵn các trường đăng nhập nếu người dùng truyền tham số dòng lệnh
    if args.username:
        gui.e_user.delete(0, "end"); gui.e_user.insert(0, args.username)
    gui.e_port.delete(0, "end");  gui.e_port.insert(0, str(args.port))
    gui.e_bhost.delete(0, "end"); gui.e_bhost.insert(0, args.bootstrap_host)
    gui.e_bport.delete(0, "end"); gui.e_bport.insert(0, str(args.bootstrap_port))

    gui.run()


if __name__ == "__main__":
    main()
