from __future__ import annotations

import base64
import os
from dataclasses import dataclass


class SecurityConfigurationError(RuntimeError):
    """Raised when secret encryption is not configured correctly."""


class CipherProtocol:
    def encrypt(self, value: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def decrypt(self, encoded: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class FernetCipher(CipherProtocol):
    key: bytes

    def __post_init__(self) -> None:
        try:
            from cryptography.fernet import Fernet  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on runtime
            raise SecurityConfigurationError(
                "Secure backend 'fernet' requires 'cryptography' package. "
                "Install it or explicitly switch to development-only insecure backend."
            ) from exc

        self._fernet = Fernet(self.key)

    def encrypt(self, value: str) -> str:
        token = self._fernet.encrypt(value.encode("utf-8"))
        return f"fernet:{token.decode('ascii')}"

    def decrypt(self, encoded: str) -> str:
        if not encoded.startswith("fernet:"):
            raise SecurityConfigurationError("Secret token format is not fernet")
        token = encoded.split(":", 1)[1].encode("ascii")
        return self._fernet.decrypt(token).decode("utf-8")


@dataclass
class XorDevCipher(CipherProtocol):
    key: bytes

    def encrypt(self, value: str) -> str:
        data = value.encode("utf-8")
        key = self.key
        mixed = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
        return f"xor:{base64.urlsafe_b64encode(mixed).decode('ascii')}"

    def decrypt(self, encoded: str) -> str:
        if not encoded.startswith("xor:"):
            raise SecurityConfigurationError("Secret token format is not xor")
        payload = encoded.split(":", 1)[1]
        data = base64.urlsafe_b64decode(payload.encode("ascii"))
        key = self.key
        mixed = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
        return mixed.decode("utf-8")


ALLOWED_DEV_ENVS = {"dev", "development", "test", "local"}


def _env_name() -> str:
    return os.getenv("BONIFACIY_ENV", "production").strip().lower()


def build_secret_cipher() -> CipherProtocol:
    backend = os.getenv("BONIFACIY_SECRET_BACKEND", "fernet").strip().lower()
    key_value = os.getenv("BONIFACIY_SECRET_KEY", "")
    if not key_value:
        raise SecurityConfigurationError("BONIFACIY_SECRET_KEY is required for secret encryption.")

    key = key_value.encode("utf-8")

    if backend == "fernet":
        return FernetCipher(key=key)

    if backend == "insecure-xor":
        env_name = _env_name()
        if env_name not in ALLOWED_DEV_ENVS:
            raise SecurityConfigurationError(
                "insecure-xor backend is forbidden outside development/test environments."
            )
        if os.getenv("BONIFACIY_ALLOW_INSECURE_SECRETS", "0") != "1":
            raise SecurityConfigurationError(
                "To use insecure-xor in development, set BONIFACIY_ALLOW_INSECURE_SECRETS=1."
            )
        return XorDevCipher(key=key)

    raise SecurityConfigurationError(f"Unsupported secret backend: {backend}")
