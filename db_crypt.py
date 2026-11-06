#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
رمزنگاری دیتابیس ربات — بدون هیچ کتابخانه خارجی
================================================
از HMAC-SHA256 به‌عنوان مولد کلید-استریم (CTR) استفاده می‌کند، پس
خروجی رمزنگاری‌شده را می‌توان امن در GitHub Actions Cache گذاشت
(در ریپوی عمومی، کش برای همه قابل دانلود است).

    python db_crypt.py encrypt tradeguard.db out.bin
    python db_crypt.py decrypt out.bin tradeguard.db
    python db_crypt.py selftest
"""

import hashlib
import hmac
import os
import sys
from pathlib import Path

MAGIC = b"TGDB1"
TAG_LEN = 32
CHUNK = 64  # بایت به ازای هر بلوک استریم


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hmac.new(key, nonce + ctr.to_bytes(8, "big"), hashlib.sha256).digest()
        ctr += 1
    return bytes(out[:n])


def encrypt_bytes(data: bytes, password: str) -> bytes:
    key = hashlib.sha256(("tgdb:" + password).encode("utf-8")).digest()
    nonce = os.urandom(16)
    ks = _keystream(key, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, ks))
    tag = hmac.new(key, MAGIC + nonce + ct, hashlib.sha256).digest()
    return MAGIC + nonce + tag + ct


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("فایل رمزنگاری‌شده نیست (امضای TGDB1 پیدا نشد)")
    nonce = blob[5:21]
    tag = blob[21:21 + TAG_LEN]
    ct = blob[21 + TAG_LEN:]
    key = hashlib.sha256(("tgdb:" + password).encode("utf-8")).digest()
    expect = hmac.new(key, MAGIC + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expect):
        raise ValueError("رمز اشتباه است یا فایل دست‌کاری شده")
    ks = _keystream(key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        import tempfile
        pwd = "test-pass-123"
        payload = (b"sqlite-format" + os.urandom(5000)) * 7
        blob = encrypt_bytes(payload, pwd)
        assert decrypt_bytes(blob, pwd) == payload, "roundtrip failed"
        assert b"sqlite-format" not in blob, "plaintext leaked"
        try:
            decrypt_bytes(blob, "wrong-pass")
            raise AssertionError("wrong password accepted!")
        except ValueError:
            pass
        tampered = bytearray(blob)
        tampered[-1] ^= 0xFF
        try:
            decrypt_bytes(bytes(tampered), pwd)
            raise AssertionError("tamper not detected!")
        except ValueError:
            pass
        empty = encrypt_bytes(b"", pwd)
        assert decrypt_bytes(empty, pwd) == b""
        print(f"✅ SELFTEST OK  ({len(payload):,} bytes, {len(blob):,} bytes ciphertext)")
        return 0

    if len(sys.argv) != 4 or sys.argv[1] not in ("encrypt", "decrypt"):
        print(__doc__)
        return 2

    mode, src, dst = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    pwd = os.environ.get("TG_DB_KEY", "").strip()
    if not pwd:
        print("❌ متغیر محیطی TG_DB_KEY تنظیم نشده")
        return 1
    if not src.exists():
        print(f"❌ فایل ورودی نیست: {src}")
        return 1
    data = src.read_bytes()
    try:
        out = encrypt_bytes(data, pwd) if mode == "encrypt" else decrypt_bytes(data, pwd)
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    print(f"✅ {mode}: {src.name} ({len(data):,} B) → {dst.name} ({len(out):,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
