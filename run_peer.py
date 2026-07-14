#!/usr/bin/env python3
"""
Khởi động một Peer Node.

Dùng:
    python run_peer.py --username Alice --port 9001
    python run_peer.py -u Bob -p 9002
    python run_peer.py -u Charlie -p 9003 --bootstrap-host 192.168.1.10
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from peer.node import PeerNode
from peer.cli import CLI
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, DEFAULT_PEER_PORT, NETWORK_SECRET

logging.basicConfig(
    level=logging.WARNING,   # Chỉ hiện WARNING trở lên trong mode thường
    format="[%(name)s] %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="P2P Chat – Peer Node")
    parser.add_argument("--username", "-u", required=True,
                        help="Tên người dùng (duy nhất trong mạng)")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PEER_PORT,
                        help=f"Cổng lắng nghe của peer (mặc định: {DEFAULT_PEER_PORT})")
    parser.add_argument("--bootstrap-host", default=BOOTSTRAP_HOST,
                        help=f"Địa chỉ bootstrap server (mặc định: {BOOTSTRAP_HOST})")
    parser.add_argument("--bootstrap-port", type=int, default=BOOTSTRAP_PORT,
                        help=f"Cổng bootstrap server (mặc định: {BOOTSTRAP_PORT})")
    parser.add_argument("--key", default=NETWORK_SECRET,
                        help="Khoá mã hoá chung của mạng (mọi peer phải giống nhau)")
    parser.add_argument("--debug", action="store_true",
                        help="Bật chế độ debug (log chi tiết)")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    node = PeerNode(
        username=args.username,
        port=args.port,
        bootstrap_host=args.bootstrap_host,
        bootstrap_port=int(args.bootstrap_port),
        secret=args.key,
    )

    if not node.start():
        sys.exit(1)

    cli = CLI(node)
    cli.run()


if __name__ == "__main__":
    main()
