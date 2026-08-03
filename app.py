"""Streamlit front door for monarch-account-summary.

Run with: streamlit run app.py

Two ways to sync:
  - Upload a CSV export from Monarch (tested, verified path).
  - Fetch live from Monarch using credentials stored in the OS credential
    store (UNVERIFIED -- no test account was available while building this;
    click-test it yourself the first time you use it).
"""

from __future__ import annotations

import glob
import tempfile
from pathlib import Path

import streamlit as st

from monarch_summary import credentials, notifications
from monarch_summary.monarch_client import fetch_transactions
from monarch_summary.pipeline import SyncOutcome, sync_from_csv, sync_from_transactions

DEFAULT_OWNERS_CONFIG = "config/owners.local.yaml"
DEFAULT_CATEGORIES_CONFIG = "config/categories.yaml"

st.set_page_config(page_title="Monarch Account Summary", page_icon="🔄")
st.title("Monarch Account Summary")


def default_workbook_path() -> str:
    matches = glob.glob("expense_data/input/*.xlsx")
    return matches[0] if len(matches) == 1 else ""


def _try_notify_failure(error: Exception) -> None:
    try:
        notifications.send_sync_failure_email(error)
        st.info("Failure alert emailed.")
    except notifications.NotificationError as e:
        st.warning(f"Could not send failure email: {e}")


def render_results(outcome: SyncOutcome) -> None:
    st.success(f"Synced. Workbook written to: `{outcome.dest}`")
    if outcome.parse_result is not None:
        pr = outcome.parse_result
        st.caption(f"Parsed {pr.total_rows} rows from CSV ({pr.skipped_blank_amount} skipped: no Amount yet).")

    cols = st.columns(3)
    for col, user in zip(cols, ("Combined", "AZS", "SSP")):
        summary = outcome.summaries[user]
        with col:
            st.metric(f"{user} spend", f"${summary['spend']:,.2f}")
            st.metric(f"{user} income", f"${summary['income']:,.2f}")

    months = sorted(
        {m for s in outcome.summaries.values() for m in s["spend_by_month"]}
    )
    if months:
        st.subheader("Spend by month")
        st.table(
            [
                {
                    "Month": m,
                    "AZS": f"${outcome.summaries['AZS']['spend_by_month'].get(m, 0.0):,.2f}",
                    "SSP": f"${outcome.summaries['SSP']['spend_by_month'].get(m, 0.0):,.2f}",
                    "Combined": f"${outcome.summaries['Combined']['spend_by_month'].get(m, 0.0):,.2f}",
                }
                for m in months
            ]
        )

    if outcome.cat_result.unmapped_categories:
        details = ", ".join(f"{c!r} ({n}x)" for c, n in sorted(outcome.cat_result.unmapped_categories.items()))
        st.warning(f"Categories not found in categories.yaml (excluded from every rollup): {details}")

    st.info(
        "Gross Income (Monthly_AZS!E5 / Monthly_SSP!E5) is a manual-entry cell in "
        "the template -- fill it in once per person in Excel for Gross Savings % "
        "to be meaningful."
    )

    with open(outcome.dest, "rb") as f:
        st.download_button("Download synced workbook", f, file_name=Path(outcome.dest).name)


try:
    has_creds = credentials.has_monarch_credentials()
    creds_error: str | None = None
except credentials.CredentialStoreUnavailable as e:
    has_creds = False
    creds_error = str(e)

with st.expander("⚙️ Settings — Monarch credentials", expanded=not has_creds):
    st.caption(
        "Stored in your OS credential store via `keyring` (Windows Credential "
        "Manager / macOS Keychain / Linux Secret Service) -- never written to "
        "a plaintext file in this app or repo."
    )
    if creds_error:
        st.error(creds_error)
    else:
        st.write("✅ Monarch credentials saved" if has_creds else "No Monarch credentials saved yet.")

    with st.form("credentials_form"):
        email_default = (credentials.get_secret(credentials.KEY_MONARCH_EMAIL) or "") if not creds_error else ""
        email = st.text_input("Monarch email", value=email_default)
        password = st.text_input("Monarch password", type="password", help="Leave blank to keep the currently saved password.")
        mfa_secret = st.text_input(
            "Monarch MFA secret key (optional)",
            type="password",
            help="The TOTP seed from your authenticator app setup, so sync can run "
                 "unattended. Leave blank if you'd rather not store it -- live fetch "
                 "then only works when MFA isn't required at login time.",
        )
        save_col, clear_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Save")
        clear_clicked = clear_col.form_submit_button("Clear stored credentials")

    if save_clicked:
        try:
            if email:
                credentials.set_secret(credentials.KEY_MONARCH_EMAIL, email)
            if password:
                credentials.set_secret(credentials.KEY_MONARCH_PASSWORD, password)
            if mfa_secret:
                credentials.set_secret(credentials.KEY_MONARCH_MFA_SECRET, mfa_secret)
            st.success("Saved. Re-open this section to confirm.")
        except credentials.CredentialStoreUnavailable as e:
            st.error(str(e))

    if clear_clicked:
        try:
            for key in (
                credentials.KEY_MONARCH_EMAIL,
                credentials.KEY_MONARCH_PASSWORD,
                credentials.KEY_MONARCH_MFA_SECRET,
            ):
                credentials.delete_secret(key)
            st.success("Cleared.")
        except credentials.CredentialStoreUnavailable as e:
            st.error(str(e))

try:
    has_gmail_creds = credentials.has_gmail_credentials()
    gmail_creds_error: str | None = None
except credentials.CredentialStoreUnavailable as e:
    has_gmail_creds = False
    gmail_creds_error = str(e)

with st.expander("⚙️ Settings — Email alerts (Gmail)", expanded=False):
    st.caption(
        "Sent via Gmail SMTP using an app password (not your regular Gmail "
        "password) -- generate one at https://myaccount.google.com/apppasswords. "
        "Stored in the same OS credential store as Monarch credentials."
    )
    if gmail_creds_error:
        st.error(gmail_creds_error)
    else:
        st.write("✅ Gmail credentials saved" if has_gmail_creds else "No Gmail credentials saved yet.")

    with st.form("gmail_credentials_form"):
        gmail_default = (credentials.get_secret(credentials.KEY_GMAIL_ADDRESS) or "") if not gmail_creds_error else ""
        recipient_default = (credentials.get_secret(credentials.KEY_ALERT_RECIPIENT) or "") if not gmail_creds_error else ""
        gmail_address = st.text_input("Gmail address", value=gmail_default)
        gmail_app_password = st.text_input(
            "Gmail app password", type="password",
            help="Leave blank to keep the currently saved app password.",
        )
        alert_recipient = st.text_input(
            "Alert recipient (optional)", value=recipient_default,
            help="Where alerts are sent. Leave blank to send to the Gmail address itself.",
        )
        gmail_save_col, gmail_clear_col = st.columns(2)
        gmail_save_clicked = gmail_save_col.form_submit_button("Save")
        gmail_clear_clicked = gmail_clear_col.form_submit_button("Clear stored credentials")

    if gmail_save_clicked:
        try:
            if gmail_address:
                credentials.set_secret(credentials.KEY_GMAIL_ADDRESS, gmail_address)
            if gmail_app_password:
                credentials.set_secret(credentials.KEY_GMAIL_APP_PASSWORD, gmail_app_password)
            if alert_recipient:
                credentials.set_secret(credentials.KEY_ALERT_RECIPIENT, alert_recipient)
            st.success("Saved. Re-open this section to confirm.")
        except credentials.CredentialStoreUnavailable as e:
            st.error(str(e))

    if gmail_clear_clicked:
        try:
            for key in (
                credentials.KEY_GMAIL_ADDRESS,
                credentials.KEY_GMAIL_APP_PASSWORD,
                credentials.KEY_ALERT_RECIPIENT,
            ):
                credentials.delete_secret(key)
            st.success("Cleared.")
        except credentials.CredentialStoreUnavailable as e:
            st.error(str(e))

    if st.button("Send test email"):
        try:
            notifications.send_test_email()
            st.success("Test email sent -- check your inbox.")
        except notifications.NotificationError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001 -- surface raw SMTP errors (auth, network) as-is
            st.error(f"Failed to send test email: {e}")

st.header("Sync")

workbook_path = st.text_input("Workbook path (.xlsx)", value=default_workbook_path())

source_mode = st.radio(
    "Transaction source",
    ["Fetch live from Monarch", "Upload a CSV export"],
    index=0 if has_creds else 1,
    help="Live fetch is UNVERIFIED -- there was no test account available while "
         "building this. CSV upload is the tested path.",
)

uploaded_file = None
if source_mode == "Upload a CSV export":
    uploaded_file = st.file_uploader("Monarch transactions CSV export", type="csv")
elif not has_creds:
    st.info("No Monarch credentials saved yet -- fill in Settings above, or switch to CSV upload.")

email_results = st.checkbox(
    "📧 Email me the results",
    value=False,
    disabled=not has_gmail_creds,
    help="Save Gmail credentials in Settings above to enable this." if not has_gmail_creds else None,
)

if st.button("🔄 Sync Now", type="primary"):
    if not workbook_path:
        st.error("Enter a workbook path first.")
    elif source_mode == "Upload a CSV export" and uploaded_file is None:
        st.error("Upload a CSV export first.")
    elif source_mode == "Fetch live from Monarch" and not has_creds:
        st.error("Save Monarch credentials in Settings first, or switch to CSV upload.")
    else:
        outcome = None
        with st.spinner("Syncing..."):
            try:
                if source_mode == "Upload a CSV export":
                    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name
                    outcome = sync_from_csv(
                        tmp_path, workbook_path, DEFAULT_OWNERS_CONFIG, DEFAULT_CATEGORIES_CONFIG
                    )
                else:
                    transactions = fetch_transactions(
                        email=credentials.get_secret(credentials.KEY_MONARCH_EMAIL),
                        password=credentials.get_secret(credentials.KEY_MONARCH_PASSWORD),
                        mfa_secret_key=credentials.get_secret(credentials.KEY_MONARCH_MFA_SECRET),
                    )
                    outcome = sync_from_transactions(
                        transactions, workbook_path, DEFAULT_OWNERS_CONFIG, DEFAULT_CATEGORIES_CONFIG
                    )
            except (FileNotFoundError, ValueError, credentials.CredentialStoreUnavailable) as e:
                st.error(f"Sync failed: {e}")
                if email_results:
                    _try_notify_failure(e)
            except Exception as e:  # noqa: BLE001 -- live Monarch connector is unverified
                st.error(
                    "Sync failed with an unexpected error. The live Monarch connector "
                    f"is unverified and this may be a gap in it: {e}"
                )
                if email_results:
                    _try_notify_failure(e)

        if outcome is not None:
            render_results(outcome)
            if email_results:
                try:
                    notifications.send_sync_success_email(outcome)
                    st.success("Summary emailed.")
                except notifications.NotificationError as e:
                    st.warning(f"Could not send summary email: {e}")
