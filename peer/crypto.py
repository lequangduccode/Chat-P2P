"""Authenticated message encryption for the P2P chat application.

Only message payloads are encrypted. Routing metadata (message type, sender,
recipient/group identifiers and timestamp) stays visible so the P2P transport
and store-and-forward queue can route messages without possessing plaintext.
"""
from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class MessageDecryptionError(ValueError):
    """Raised when a ciphertext cannot be authenticated or decrypted."""


@dataclass(frozen=True)
class CryptoInfo:
    algorithm: str = "AES-256-GCM"
    version: int = 1


class MessageCrypto:
    """AES-256-GCM encryption derived from a shared network passphrase.

    A deterministic 256-bit key is derived from the passphrase with PBKDF2.
    Every message receives a fresh random 96-bit nonce, which is mandatory for
    AES-GCM security. Associated data binds ciphertext to stable routing fields
    so those fields cannot be silently altered without decryption failing.
    """

    INFO = CryptoInfo()
    _SALT = b"Chat-P2P::AES-GCM::v1"
    _ITERATIONS = 390_000

    def __init__(self, passphrase: str):
        if not isinstance(passphrase, str) or len(passphrase) < 8:
            raise ValueError("Khóa mã hóa phải có ít nhất 8 ký tự")
        key = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            self._SALT,
            self._ITERATIONS,
            dklen=32,
        )
        self._aes = AESGCM(key)
        # A non-secret fingerprint helps users verify that peers use one key.
        self.fingerprint = hashlib.sha256(key).hexdigest()[:12].upper()

    @staticmethod
    def _aad(message: dict) -> bytes:
        fields = (
            str(message.get("type", "")),
            str(message.get("from_name", "")),
            str(message.get("to_id", "")),
            str(message.get("group_id", "")),
            str(message.get("timestamp", "")),
        )
        return "|".join(fields).encode("utf-8")

    def encrypt_content(self, message: dict) -> dict:
        """Return a copy with `content` replaced by authenticated ciphertext."""
        if message.get("encrypted"):
            return dict(message)
        plaintext = str(message.get("content", "")).encode("utf-8")
        nonce = os.urandom(12)
        encrypted = self._aes.encrypt(nonce, plaintext, self._aad(message))
        result = dict(message)
        result.pop("content", None)
        result.update(
            encrypted=True,
            encryption=self.INFO.algorithm,
            crypto_version=self.INFO.version,
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(encrypted).decode("ascii"),
        )
        return result

    def decrypt_content(self, message: dict) -> dict:
        """Return a copy containing plaintext `content`.

        Plaintext legacy messages pass through unchanged for compatibility.
        """
        if not message.get("encrypted"):
            return dict(message)
        if message.get("encryption") != self.INFO.algorithm:
            raise MessageDecryptionError("Thuật toán mã hóa không được hỗ trợ")
        try:
            nonce = base64.b64decode(message["nonce"], validate=True)
            ciphertext = base64.b64decode(message["ciphertext"], validate=True)
            plaintext = self._aes.decrypt(nonce, ciphertext, self._aad(message))
        except (KeyError, ValueError, InvalidTag) as exc:
            raise MessageDecryptionError(
                "Không thể giải mã tin nhắn: khóa không khớp hoặc dữ liệu đã bị thay đổi"
            ) from exc
        result = dict(message)
        result["content"] = plaintext.decode("utf-8")
        return result
