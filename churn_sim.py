#!/usr/bin/env python3
"""
Mô phỏng churn – peer tham gia và rời mạng liên tục.

Tạo N "bot" peer chạy nền (không GUI). Mỗi bot lặp vô hạn trong thời gian demo:
    kết nối  →  ở lại vài giây  →  (thỉnh thoảng gửi broadcast)  →  rời mạng
    →  chờ vài giây  →  kết nối lại …

Dùng để chứng minh tính chịu lỗi: trong khi các peer GUI thật đang chat,
danh sách online sẽ liên tục thay đổi (>> X tham gia / >> X rời mạng) mà
hệ thống vẫn hoạt động ổn định.

Dùng:
    python churn_sim.py                     # 3 bot, chạy 60s
    python churn_sim.py --peers 5 --duration 120
    python churn_sim.py --bootstrap-host 172.17.9.8
"""

import sys
import os
import time
import random
import argparse
import threading
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.CRITICAL)   # tắt log ồn của node

from peer.node import PeerNode
from config import BOOTSTRAP_HOST, BOOTSTRAP_PORT, NETWORK_SECRET

_print_lock = threading.Lock()


def log(msg: str):
    with _print_lock:
        print(msg, flush=True)


def churn_bot(name: str, port: int, bhost: str, bport: int,
              secret: str, deadline: float):
    """Một bot: vòng lặp join/leave cho tới khi hết giờ."""
    rnd = random.Random(port)          # mỗi bot một chuỗi ngẫu nhiên riêng
    round_no = 0
    while time.time() < deadline:
        round_no += 1
        node = PeerNode(name, port, bhost, bport, secret=secret)
        if not node.start():
            log(f"  [{name}] ✗ không kết nối được bootstrap, thử lại sau…")
            time.sleep(2)
            continue

        stay = rnd.uniform(3, 9)
        log(f"  [{name}] ● JOIN  (vòng {round_no}, ở lại {stay:.0f}s)")

        # thỉnh thoảng phát 1 tin để chứng minh vẫn gửi được trong lúc churn
        t_end = time.time() + stay
        while time.time() < t_end and time.time() < deadline:
            time.sleep(min(3, t_end - time.time()))
            if rnd.random() < 0.5:
                peers = node.get_online_peers()
                if peers:
                    node.broadcast(f"(churn) {name} còn sống, thấy {len(peers)} peer")

        node.stop()
        away = rnd.uniform(2, 6)
        log(f"  [{name}] ○ LEAVE (nghỉ {away:.0f}s)")
        time.sleep(away)

    log(f"  [{name}] ■ kết thúc mô phỏng")


def main():
    ap = argparse.ArgumentParser(description="P2P Chat – Churn Simulator")
    ap.add_argument("--peers", type=int, default=3, help="Số bot (mặc định 3)")
    ap.add_argument("--duration", type=int, default=60,
                    help="Thời lượng mô phỏng, giây (mặc định 60)")
    ap.add_argument("--base-port", type=int, default=9600,
                    help="Cổng bắt đầu cho các bot (mặc định 9600)")
    ap.add_argument("--bootstrap-host", default=BOOTSTRAP_HOST)
    ap.add_argument("--bootstrap-port", type=int, default=BOOTSTRAP_PORT)
    ap.add_argument("--key", default=NETWORK_SECRET)
    args = ap.parse_args()

    deadline = time.time() + args.duration
    log(f"=== CHURN SIM: {args.peers} bot, {args.duration}s, "
        f"bootstrap {args.bootstrap_host}:{args.bootstrap_port} ===")

    threads = []
    for i in range(args.peers):
        name = f"Bot-{i+1}"
        port = args.base_port + i
        t = threading.Thread(
            target=churn_bot,
            args=(name, port, args.bootstrap_host, args.bootstrap_port,
                  args.key, deadline),
            daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.4)   # lệch pha để join/leave đan xen

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        log("\n=== Dừng mô phỏng ===")
    log("=== Xong ===")


if __name__ == "__main__":
    main()
