from app.store.settings_secrets import SecretStore


def test_get_with_fallback_returns_primary(monkeypatch):
    values = {
        ("realtime-translation", "transcribe"): "primary-key",
        ("realtime-translation", "default"): "legacy-key",
    }

    monkeypatch.setattr(
        "app.store.settings_secrets.keyring.get_password",
        lambda service, name: values.get((service, name)),
    )

    store = SecretStore()

    assert store.get_with_fallback("transcribe", "default") == "primary-key"


def test_get_with_fallback_promotes_legacy(monkeypatch):
    values = {
        ("realtime-translation", "default"): "legacy-key",
    }
    saved = {}

    monkeypatch.setattr(
        "app.store.settings_secrets.keyring.get_password",
        lambda service, name: values.get((service, name)),
    )
    monkeypatch.setattr(
        "app.store.settings_secrets.keyring.set_password",
        lambda service, name, value: saved.__setitem__((service, name), value),
    )

    store = SecretStore()

    assert store.get_with_fallback("translate", "default", promote=True) == "legacy-key"
    assert saved[("realtime-translation", "translate")] == "legacy-key"


def test_set_empty_value_deletes_secret(monkeypatch):
    deleted = []

    monkeypatch.setattr(
        "app.store.settings_secrets.keyring.delete_password",
        lambda service, name: deleted.append((service, name)),
    )

    store = SecretStore()
    store.set("translate", "")

    assert deleted == [("realtime-translation", "translate")]
