#!/usr/bin/env python3
"""
Khởi động Bootstrap Server.

Dùng:
    python run_bootstrap.py
    python run_bootstrap.py --host 0.0.0.0 --port 9000
"""

import sys
import os
import argparse

# Đảm bảo có thể import các module trong project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bootstrap.server import BootstrapServer
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT


def main():
    parser = argparse.ArgumentParser(description="P2P Chat – Bootstrap Server")
    parser.add_argument("--host", default=BOOTSTRAP_HOST,
                        help=f"Host lắng nghe (mặc định: {BOOTSTRAP_HOST})")
    parser.add_argument("--port", type=int, default=BOOTSTRAP_PORT,
                        help=f"Cổng lắng nghe (mặc định: {BOOTSTRAP_PORT})")
    args = parser.parse_args()

    server = BootstrapServer(args.host, args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Bootstrap] Đã dừng.")


if __name__ == "__main__":
    main()
