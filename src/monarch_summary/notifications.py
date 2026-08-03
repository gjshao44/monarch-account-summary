"""Email alerts via Gmail SMTP, using an app password stored in the OS keyring.

Reuses credentials.py's keyring-backed secret storage (its docstring already
anticipated this: "works for Monarch credentials now and Gmail credentials
later without any redesign").
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from monarch_summary import credentials
from monarch_summary.pipeline import SyncOutcome

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class NotificationError(RuntimeError):
    """Raised when an email can't be sent (missing credentials/recipient, SMTP failure)."""


def _resolve_recipient(to_addr: str | None) -> str:
    sender = credentials.get_secret(credentials.KEY_GMAIL_ADDRESS)
    return to_addr or credentials.get_secret(credentials.KEY_ALERT_RECIPIENT) or sender or ""


def send_email(subject: str, body: str, to_addr: str | None = None) -> None:
    """Send a plaintext email via Gmail SMTP using stored app-password credentials."""
    sender = credentials.get_secret(credentials.KEY_GMAIL_ADDRESS)
    app_password = credentials.get_secret(credentials.KEY_GMAIL_APP_PASSWORD)
    if not sender or not app_password:
        raise NotificationError(
            "Gmail credentials missing: save a Gmail address and app password "
            "in Settings before enabling email alerts."
        )

    recipient = _resolve_recipient(to_addr)
    if not recipient:
        raise NotificationError(
            "No recipient email: save an alert recipient in Settings, or pass "
            "to_addr explicitly."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.send_message(msg)


def summary_email_body(outcome: SyncOutcome) -> str:
    """Same content as the CLI's/UI's on-screen summary, as plain text."""
    lines: list[str] = []
    pr = outcome.parse_result
    if pr is not None:
        lines.append(
            f"Parsed {pr.total_rows} rows from CSV "
            f"({pr.skipped_blank_amount} skipped: no Amount yet)."
        )

    for user in ("AZS", "SSP", "Combined"):
        summary = outcome.summaries[user]
        label = "Combined (AZS + SSP)" if user == "Combined" else user
        rows_note = f"{summary['row_count']} rows written | " if user != "Combined" else ""
        lines.append(
            f"\n{label}: {rows_note}"
            f"spend ${summary['spend']:,.2f} | income (from transactions) ${summary['income']:,.2f}"
        )
        for month, amount in summary["spend_by_month"].items():
            lines.append(f"    {month}: ${amount:,.2f}")

    if outcome.cat_result.unmapped_categories:
        lines.append(
            "\nWARNING: categories not found in categories.yaml (excluded from "
            "every rollup, add them if that's wrong):"
        )
        for cat, count in sorted(outcome.cat_result.unmapped_categories.items()):
            lines.append(f"    {cat!r} ({count}x)")

    lines.append(f"\nWorkbook written to: {outcome.dest}")
    return "\n".join(lines)


def send_sync_success_email(outcome: SyncOutcome, to_addr: str | None = None) -> None:
    combined = outcome.summaries["Combined"]
    subject = f"Monarch sync complete: ${combined['spend']:,.2f} spend"
    if outcome.cat_result.unmapped_categories:
        subject += " (unmapped categories found)"
    send_email(subject, summary_email_body(outcome), to_addr=to_addr)


def send_sync_failure_email(error: Exception, to_addr: str | None = None) -> None:
    send_email("Monarch sync failed", f"Sync failed with an error:\n\n{error}", to_addr=to_addr)


def send_test_email(to_addr: str | None = None) -> None:
    send_email(
        "Monarch Account Summary: test email",
        "This is a test email from monarch-account-summary. If you're reading "
        "this, Gmail alerting is configured correctly.",
        to_addr=to_addr,
    )
