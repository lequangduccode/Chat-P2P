"""
Message framing: 4-byte big-endian length prefix + UTF-8 JSON payload.
All messages are dicts with a required "type" field.
"""
import json
import uuid
import struct
from datetime import datetime


class MsgType:
    # Bootstrap <-> Peer
    REGISTER      = "REGISTER"
    REGISTER_OK   = "REGISTER_OK"
    UNREGISTER    = "UNREGISTER"
    GET_PEERS     = "GET_PEERS"
    PEER_LIST     = "PEER_LIST"
    HEARTBEAT     = "HEARTBEAT"
    HEARTBEAT_OK  = "HEARTBEAT_OK"

    # Bootstrap pushes these to all peers
    PEER_JOINED   = "PEER_JOINED"
    PEER_LEFT     = "PEER_LEFT"

    # Peer <-> Peer
    DIRECT_MSG    = "DIRECT_MSG"
    GROUP_MSG     = "GROUP_MSG"
    GROUP_INVITE  = "GROUP_INVITE"
    FILE_MSG      = "FILE_MSG"

    # Generic
    ACK           = "ACK"
    ERROR         = "ERROR"


def make_msg(msg_type: str, **kwargs) -> dict:
    return {"type": msg_type, **kwargs}


def encode_msg(msg: dict) -> bytes:
    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def recv_msg(sock) -> dict | None:
    """Blocking receive of one framed message. Returns None on error/close."""
    header = _recv_exact(sock, 4)
    if not header:
        return None
    length = struct.unpack(">I", header)[0]
    if length == 0 or length > 10_000_000:
        return None
    payload = _recv_exact(sock, length)
    if not payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


def _recv_exact(sock, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        except Exception:
            return None
    return buf


def new_id() -> str:
    return str(uuid.uuid4())


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")
