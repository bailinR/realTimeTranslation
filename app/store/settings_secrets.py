from __future__ import annotations

import keyring

from app.config import SECRET_SERVICE


class SecretStore:
    def get(self, name: str) -> str:
        return keyring.get_password(SECRET_SERVICE, name) or ""

    def get_with_fallback(self, name: str, *fallback_names: str, promote: bool = False) -> str:
        value = self.get(name)
        if value:
            return value
        for fallback_name in fallback_names:
            if not fallback_name or fallback_name == name:
                continue
            value = self.get(fallback_name)
            if value:
                if promote:
                    self.set(name, value)
                return value
        return ""

    def set(self, name: str, value: str) -> None:
        if value:
            keyring.set_password(SECRET_SERVICE, name, value)
        else:
            self.delete(name)

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(SECRET_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
