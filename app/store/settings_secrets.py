from __future__ import annotations

import keyring

from app.config import SECRET_SERVICE


class SecretStore:
    def get(self, name: str) -> str:
        return keyring.get_password(SECRET_SERVICE, name) or ""

    def set(self, name: str, value: str) -> None:
        if value:
            keyring.set_password(SECRET_SERVICE, name, value)

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(SECRET_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
