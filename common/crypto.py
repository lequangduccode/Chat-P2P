"""
Mã hoá tin nhắn – CHỈ dùng thư viện chuẩn của Python (hashlib, hmac, secrets).

Không có AES trong stdlib, nên dùng một sơ đồ mã hoá xác thực (authenticated
encryption) tự xây từ các primitive chuẩn – đủ để minh hoạ cho đồ án:

  1. Khoá gốc  : PBKDF2-HMAC-SHA256(passphrase)      -> 32 byte
  2. Tách khoá : k_enc = HMAC(master,"enc"), k_mac = HMAC(master,"mac")
  3. Keystream : HMAC-SHA256(k_enc, nonce || counter) theo chế độ đếm (CTR)
  4. Mã hoá    : ciphertext = plaintext XOR keystream
  5. Xác thực  : tag = HMAC-SHA256(k_mac, nonce || ciphertext)   (Encrypt-then-MAC)

Gói dữ liệu trên đường truyền: base64( nonce[16] || ciphertext || tag[32] ).
Giải mã kiểm tra tag trước (chống giả mạo); sai khoá / sửa dữ liệu -> trả None.

Lưu ý: đây là bản dựng phục vụ học tập, không dùng cho hệ thống thật.
"""

import base64
import hashlib
import hmac
import secrets

_NONCE = 16
_TAG = 32
_SALT = b"p2p-chat-nhom7-salt"     # cố định để mọi peer suy ra cùng khoá
_ITERS = 100_000


def derive_key(passphrase: str) -> bytes:
    """Suy ra khoá gốc 32 byte từ passphrase chung của mạng."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"),
                               _SALT, _ITERS, dklen=32)


def _subkeys(master: bytes):
    k_enc = hmac.new(master, b"enc", hashlib.sha256).digest()
    k_mac = hmac.new(master, b"mac", hashlib.sha256).digest()
    return k_enc, k_mac


def _keystream(k_enc: bytes, nonce: bytes, n: int) -> bytes:
    """Sinh n byte keystream: HMAC(k_enc, nonce || counter) nối tiếp."""
    out = bytearray()
    counter = 0
    while len(out) < n:
        block = hmac.new(k_enc,
                         nonce + counter.to_bytes(4, "big"),
                         hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:n])


def encrypt_bytes(data: bytes, master: bytes) -> bytes:
    k_enc, k_mac = _subkeys(master)
    nonce = secrets.token_bytes(_NONCE)
    ks = _keystream(k_enc, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, ks))
    tag = hmac.new(k_mac, nonce + ct, hashlib.sha256).digest()
    return nonce + ct + tag


def decrypt_bytes(blob: bytes, master: bytes) -> bytes | None:
    if len(blob) < _NONCE + _TAG:
        return None
    nonce = blob[:_NONCE]
    tag = blob[-_TAG:]
    ct = blob[_NONCE:-_TAG]
    k_enc, k_mac = _subkeys(master)
    expect = hmac.new(k_mac, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expect):   # so sánh chống timing attack
        return None
    ks = _keystream(k_enc, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


# ---------------------------------------------------------------- Text helpers

def encrypt(text: str, master: bytes) -> str:
    """Mã hoá chuỗi -> chuỗi base64 an toàn để nhét vào JSON."""
    return base64.b64encode(encrypt_bytes(text.encode("utf-8"), master)).decode("ascii")


def decrypt(token: str, master: bytes) -> str | None:
    """Giải mã chuỗi base64. Trả None nếu sai khoá hoặc dữ liệu bị sửa."""
    try:
        pt = decrypt_bytes(base64.b64decode(token), master)
    except Exception:
        return None
    if pt is None:
        return None
    try:
        return pt.decode("utf-8")
    except Exception:
        return None
