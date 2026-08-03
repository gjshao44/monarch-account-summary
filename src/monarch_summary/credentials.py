"""Secret storage via the OS-native credential store (Windows Credential
Manager / macOS Keychain / Linux Secret Service) through the `keyring`
package -- never plaintext files or env vars.

Generic key/value API so it works for Monarch credentials now and Gmail
credentials later without any redesign.
"""

from __future__ import annotations

import keyring
import keyring.errors

SERVICE_NAME = "monarch-account-summary"

KEY_MONARCH_EMAIL = "monarch_email"
KEY_MONARCH_PASSWORD = "monarch_password"
KEY_MONARCH_MFA_SECRET = "monarch_mfa_secret"


class CredentialStoreUnavailable(RuntimeError):
    """Raised when the OS has no usable credential store backend."""


def _wrap(fn, *args):
    try:
        return fn(*args)
    except keyring.errors.KeyringError as e:
        raise CredentialStoreUnavailable(
            "No OS credential store is available. On native Windows Python "
            "this should work automatically via Windows Credential Manager; "
            "on macOS it uses Keychain. If you're seeing this on Linux/WSL, "
            "a Secret Service backend (e.g. gnome-keyring) needs to be "
            f"installed and running. ({e})"
        ) from e


def get_secret(key: str) -> str | None:
    return _wrap(keyring.get_password, SERVICE_NAME, key)


def set_secret(key: str, value: str) -> None:
    _wrap(keyring.set_password, SERVICE_NAME, key, value)


def delete_secret(key: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, key)
    except keyring.errors.PasswordDeleteError:
        pass  # already absent -- deleting a not-set secret is a no-op
    except keyring.errors.KeyringError as e:
        raise CredentialStoreUnavailable(str(e)) from e


def has_monarch_credentials() -> bool:
    return bool(get_secret(KEY_MONARCH_EMAIL)) and bool(get_secret(KEY_MONARCH_PASSWORD))
