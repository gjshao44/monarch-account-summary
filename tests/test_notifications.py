"""Tests mock keyring and smtplib directly -- no real email is ever sent."""

import keyring.errors
import pytest

from monarch_summary import credentials, notifications
from monarch_summary.pipeline import sync_from_csv


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


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args = None
        self.sent_message = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent_message = msg


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def _save_gmail_creds(sender="sender@gmail.com", password="app-pw", recipient=None):
    credentials.set_secret(credentials.KEY_GMAIL_ADDRESS, sender)
    credentials.set_secret(credentials.KEY_GMAIL_APP_PASSWORD, password)
    if recipient:
        credentials.set_secret(credentials.KEY_ALERT_RECIPIENT, recipient)


def test_send_email_without_credentials_raises(fake_keyring, fake_smtp):
    with pytest.raises(notifications.NotificationError, match="Gmail credentials missing"):
        notifications.send_email("subject", "body")
    assert FakeSMTP.instances == []


def test_send_email_success_uses_stored_credentials(fake_keyring, fake_smtp):
    _save_gmail_creds()
    notifications.send_email("Hello", "World")

    smtp = FakeSMTP.instances[0]
    assert smtp.host == notifications.GMAIL_SMTP_HOST
    assert smtp.port == notifications.GMAIL_SMTP_PORT
    assert smtp.started_tls is True
    assert smtp.login_args == ("sender@gmail.com", "app-pw")
    assert smtp.sent_message["Subject"] == "Hello"
    assert smtp.sent_message["From"] == "sender@gmail.com"
    assert smtp.sent_message["To"] == "sender@gmail.com"  # falls back to sender
    assert smtp.sent_message.get_content().strip() == "World"


def test_send_email_prefers_explicit_recipient_over_saved_default(fake_keyring, fake_smtp):
    _save_gmail_creds(recipient="alerts@example.com")
    notifications.send_email("Hello", "World", to_addr="override@example.com")

    assert FakeSMTP.instances[0].sent_message["To"] == "override@example.com"


def test_send_email_uses_saved_alert_recipient(fake_keyring, fake_smtp):
    _save_gmail_creds(recipient="alerts@example.com")
    notifications.send_email("Hello", "World")

    assert FakeSMTP.instances[0].sent_message["To"] == "alerts@example.com"


def test_send_test_email(fake_keyring, fake_smtp):
    _save_gmail_creds()
    notifications.send_test_email()

    msg = FakeSMTP.instances[0].sent_message
    assert "test email" in msg["Subject"].lower()


def test_send_sync_success_email(fake_keyring, fake_smtp, fixtures_dir, tmp_path):
    from conftest import build_tiny_workbook

    _save_gmail_creds()
    workbook_path = tmp_path / "workbook.xlsx"
    build_tiny_workbook(workbook_path, capacity=10)
    outcome = sync_from_csv(
        transactions_csv_path=fixtures_dir / "sample_transactions.csv",
        workbook_path=workbook_path,
        owners_config_path=fixtures_dir / "owners.test.yaml",
        categories_config_path=fixtures_dir / "categories.test.yaml",
        output_path=tmp_path / "out.xlsx",
    )

    notifications.send_sync_success_email(outcome)

    msg = FakeSMTP.instances[0].sent_message
    assert "spend" in msg["Subject"]
    assert "unmapped categories found" in msg["Subject"]  # sample fixture has one
    body = msg.get_content()
    assert "AZS" in body and "SSP" in body and "Combined" in body
    assert "Weird Category" in body


def test_send_sync_failure_email_includes_error_text(fake_keyring, fake_smtp):
    _save_gmail_creds()
    notifications.send_sync_failure_email(ValueError("boom"))

    msg = FakeSMTP.instances[0].sent_message
    assert "failed" in msg["Subject"].lower()
    assert "boom" in msg.get_content()
