import json
from pathlib import Path

from src.infrastructure.secret_store import SecretStore


class TestSecretStore:
    def _make_store(
        self, tmp_path: Path, key: str = "test-key-16-chars!!"
    ) -> SecretStore:
        return SecretStore(store_path=tmp_path / "secrets.json", encryption_key=key)

    def test_set_and_get(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.set("api_key", "sk-123")
        assert store.get("api_key") == "sk-123"

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        assert store.get("nonexistent") is None

    def test_delete(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.set("key1", "value1")
        store.delete("key1")
        assert store.get("key1") is None

    def test_delete_nonexistent_is_noop(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.delete("nope")

    def test_overwrite(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.set("k", "v1")
        store.set("k", "v2")
        assert store.get("k") == "v2"

    def test_multiple_keys(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.set("a", "1")
        store.set("b", "2")
        assert store.get("a") == "1"
        assert store.get("b") == "2"

    def test_data_is_encrypted_on_disk(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        store.set("secret", "plaintext-value")
        raw = json.loads((tmp_path / "secrets.json").read_text())
        assert raw["secret"] != "plaintext-value"

    def test_empty_encryption_key_stores_plaintext(self, tmp_path: Path) -> None:
        store = SecretStore(
            store_path=tmp_path / "secrets.json", encryption_key=""
        )
        store.set("k", "v")
        raw = json.loads((tmp_path / "secrets.json").read_text())
        assert raw["k"] == "v"

    def test_derive_key_returns_32_bytes_base64(self) -> None:
        key = SecretStore._derive_key("test-key-16-chars!!")
        assert len(key) == 44  # base64 of 32 bytes

    def test_derive_key_pads_short_input(self) -> None:
        key = SecretStore._derive_key("short")
        assert len(key) == 44

    def test_derive_key_truncates_long_input(self) -> None:
        key = SecretStore._derive_key("a" * 100)
        assert len(key) == 44

    def test_store_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c" / "secrets.json"
        store = SecretStore(store_path=nested, encryption_key="k" * 16)
        store.set("x", "y")
        assert nested.exists()
