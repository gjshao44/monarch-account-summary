"""Tests mock keyring directly since this dev box has no real OS credential
store backend available (confirmed: keyring.errors.NoKeyringError)."""

import keyring.errors
import pytest

from monarch_summary import credentials


class FakeBackend:
    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, key):
        return self.store.get((service, key))

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def delete_password(self, service, key):
        if (service, key) not in self.store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.store[(service, key)]


@pytest.fixture
def fake_keyring(monkeypatch):
    backend = FakeBackend()
    monkeypatch.setattr(credentials.keyring, "get_password", backend.get_password)
    monkeypatch.setattr(credentials.keyring, "set_password", backend.set_password)
    monkeypatch.setattr(credentials.keyring, "delete_password", backend.delete_password)
    return backend


def test_set_and_get_round_trip(fake_keyring):
    credentials.set_secret(credentials.KEY_MONARCH_EMAIL, "user@example.com")
    assert credentials.get_secret(credentials.KEY_MONARCH_EMAIL) == "user@example.com"


def test_get_missing_returns_none(fake_keyring):
    assert credentials.get_secret(credentials.KEY_MONARCH_EMAIL) is None


def test_delete_missing_is_a_noop(fake_keyring):
    credentials.delete_secret(credentials.KEY_MONARCH_EMAIL)  # must not raise


def test_delete_then_get_returns_none(fake_keyring):
    credentials.set_secret(credentials.KEY_MONARCH_PASSWORD, "hunter2")
    credentials.delete_secret(credentials.KEY_MONARCH_PASSWORD)
    assert credentials.get_secret(credentials.KEY_MONARCH_PASSWORD) is None


def test_has_monarch_credentials_requires_both(fake_keyring):
    assert credentials.has_monarch_credentials() is False
    credentials.set_secret(credentials.KEY_MONARCH_EMAIL, "user@example.com")
    assert credentials.has_monarch_credentials() is False
    credentials.set_secret(credentials.KEY_MONARCH_PASSWORD, "hunter2")
    assert credentials.has_monarch_credentials() is True


def test_no_backend_raises_credential_store_unavailable(monkeypatch):
    def raise_no_backend(*args):
        raise keyring.errors.NoKeyringError("no backend")

    monkeypatch.setattr(credentials.keyring, "get_password", raise_no_backend)
    with pytest.raises(credentials.CredentialStoreUnavailable):
        credentials.get_secret(credentials.KEY_MONARCH_EMAIL)
