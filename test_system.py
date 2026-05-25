"""
Kiểm thử tự động hệ thống Chat P2P.
Chạy: python test_system.py

Test bao gồm:
  1. Encode/decode message protocol
  2. Bootstrap server khởi động và nhận đăng ký
  3. Peer đăng ký và lấy danh sách
  4. Chat trực tiếp giữa 2 peer
  5. Chat nhóm (broadcast tới members)
  6. Phát hiện peer offline (store-and-forward)
  7. Retry khi gửi thất bại
"""

import sys
import os
import time
import threading
import socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.protocol import (MsgType, make_msg, encode_msg, recv_msg,
                              new_id, now_str)
from bootstrap.server import BootstrapServer
from peer.node import PeerNode

PASS = "[PASS]"
FAIL = "[FAIL]"

errors = []

def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        print(f"  {FAIL}  {name}" + (f" — {detail}" if detail else ""))
        errors.append(name)

# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Protocol encode/decode
# ──────────────────────────────────────────────────────────────────────────────
print("\n[1] Protocol encode/decode")

import struct, json
msg = make_msg(MsgType.DIRECT_MSG, from_name="Alice", content="Xin chào!", timestamp="12:00:00")
data = encode_msg(msg)
length = struct.unpack(">I", data[:4])[0]
decoded = json.loads(data[4:4+length])

check("type field",    decoded["type"]    == MsgType.DIRECT_MSG)
check("content field", decoded["content"] == "Xin chào!")
check("4-byte header", length == len(data) - 4)

# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Bootstrap server
# ──────────────────────────────────────────────────────────────────────────────
print("\n[2] Bootstrap server")

BS_HOST, BS_PORT = "127.0.0.1", 19000
bs = BootstrapServer(BS_HOST, BS_PORT)
threading.Thread(target=bs.start, daemon=True).start()
time.sleep(0.3)

def bs_connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((BS_HOST, BS_PORT))
    s.settimeout(5)
    return s

# Đăng ký peer giả
pid_a = new_id()
s = bs_connect()
s.sendall(encode_msg(make_msg(MsgType.REGISTER,
    peer_id=pid_a, username="TestAlice", host="127.0.0.1", port=19001)))
resp = recv_msg(s); s.close()
check("register OK",   resp and resp["type"] == MsgType.REGISTER_OK)
check("peer_id match", resp and resp.get("peer_id") == pid_a)

# Heartbeat
s = bs_connect()
s.sendall(encode_msg(make_msg(MsgType.HEARTBEAT, peer_id=pid_a)))
resp = recv_msg(s); s.close()
check("heartbeat OK",  resp and resp["type"] == MsgType.HEARTBEAT_OK)

# GET_PEERS
pid_b = new_id()
s = bs_connect()
s.sendall(encode_msg(make_msg(MsgType.REGISTER,
    peer_id=pid_b, username="TestBob", host="127.0.0.1", port=19002)))
recv_msg(s); s.close()

s = bs_connect()
s.sendall(encode_msg(make_msg(MsgType.GET_PEERS, peer_id=pid_a)))
resp = recv_msg(s); s.close()
check("get_peers returns list",    resp and resp["type"] == MsgType.PEER_LIST)
check("get_peers excludes self",   resp and all(p["peer_id"] != pid_a for p in resp["peers"]))
check("get_peers includes others", resp and any(p["peer_id"] == pid_b for p in resp["peers"]))

# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Peer Node – kết nối và chat
# ──────────────────────────────────────────────────────────────────────────────
print("\n[3] Peer Node – chat trực tiếp")

received_msgs = []

node_alice = PeerNode("Alice", 19010, BS_HOST, BS_PORT)
node_bob   = PeerNode("Bob",   19011, BS_HOST, BS_PORT)

# Bắt tin nhắn nhận được
node_bob.set_display(lambda text: received_msgs.append(text))

ok_a = node_alice.start()
ok_b = node_bob.start()
check("Alice start()", ok_a)
check("Bob start()",   ok_b)

time.sleep(0.5)   # chờ peer list cập nhật

# Alice gửi cho Bob
err = node_alice.send_direct("Bob", "Hello Bob!")
check("send_direct returns None (success)", err is None, str(err))

time.sleep(0.3)
check("Bob nhận được tin nhắn",
      any("Hello Bob!" in m for m in received_msgs),
      f"received: {received_msgs}")

# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Peer discovery (PEER_JOINED notification)
# ──────────────────────────────────────────────────────────────────────────────
print("\n[4] Peer discovery – PEER_JOINED notification")

join_events = []
node_alice.set_display(lambda text: join_events.append(text))

node_charlie = PeerNode("Charlie", 19012, BS_HOST, BS_PORT)
node_charlie.start()
time.sleep(0.5)

check("Alice nhận PEER_JOINED khi Charlie vào",
      any("Charlie" in e for e in join_events),
      f"events: {join_events}")

# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Chat nhóm
# ──────────────────────────────────────────────────────────────────────────────
print("\n[5] Chat nhóm")

group_msgs_bob     = []
group_msgs_charlie = []
node_bob.set_display(lambda text: group_msgs_bob.append(text))
node_charlie.set_display(lambda text: group_msgs_charlie.append(text))

err = node_alice.create_group("Team", ["Bob", "Charlie"])
check("create_group returns None (success)", err is None, str(err))
time.sleep(0.3)

err = node_alice.send_group("Team", "Họp nhóm!")
check("send_group returns None (success)", err is None, str(err))
time.sleep(0.3)

check("Bob nhận group message",
      any("Họp nhóm!" in m for m in group_msgs_bob))
check("Charlie nhận group message",
      any("Họp nhóm!" in m for m in group_msgs_charlie))

# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Store-and-forward (offline message)
# ──────────────────────────────────────────────────────────────────────────────
print("\n[6] Store-and-forward (offline message)")

node_charlie.stop()
time.sleep(0.2)

# Alice gửi trong khi Charlie offline
err = node_alice.send_direct("Charlie", "Tin offline cho Charlie")
check("Gửi cho offline peer trả về error message (không crash)",
      err is not None and "offline" in err.lower(), str(err))

# Kiểm tra tin nhắn đã được lưu
check("Tin nhắn offline được lưu trong pending",
      node_alice.client.has_pending(node_charlie.peer_id))

# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Retry mechanism
# ──────────────────────────────────────────────────────────────────────────────
print("\n[7] Retry mechanism")

from peer.client import PeerClient
test_client = PeerClient(BS_HOST, BS_PORT)
test_msg = make_msg(MsgType.DIRECT_MSG, from_name="X", content="test",
                    timestamp=now_str(), msg_id=new_id())

start = time.time()
result = test_client.send_to_peer("127.0.0.1", 19999, test_msg, retries=2)
elapsed = time.time() - start

check("Retry thất bại trả về False", result is False)
check("Retry có back-off delay (>= 0.5s)", elapsed >= 0.5,
      f"elapsed={elapsed:.2f}s")

# ──────────────────────────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────────────────────────
node_alice.stop()
node_bob.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Kết quả
# ──────────────────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"KET QUA: {len(errors)} test that bai: {errors}")
    sys.exit(1)
else:
    print("KET QUA: Tat ca test deu PASS!")
    sys.exit(0)
