from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet

_SALT = b"vpnbot-secret-store-v1"


class SecretStore:
    def __init__(self, store_path: Path, encryption_key: str) -> None:
        self.store_path = store_path
        self.encryption_key = encryption_key

    def get(self, key: str) -> str | None:
        data = self._load()
        value = data.get(key)
        if value is None:
            return None
        if not self.encryption_key:
            return value
        fernet = Fernet(self._derive_key(self.encryption_key))
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")

    def set(self, key: str, value: str) -> None:
        data = self._load()
        if self.encryption_key:
            fernet = Fernet(self._derive_key(self.encryption_key))
            data[key] = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        else:
            data[key] = value
        self._save(data)

    def delete(self, key: str) -> None:
        data = self._load()
        if key in data:
            data.pop(key)
            self._save(data)

    def _load(self) -> dict[str, str]:
        if not self.store_path.exists():
            return {}
        return json.loads(self.store_path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, str]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _derive_key(encryption_key: str) -> bytes:
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            encryption_key.encode("utf-8"),
            _SALT,
            iterations=100_000,
            dklen=32,
        )
        return base64.urlsafe_b64encode(derived)
