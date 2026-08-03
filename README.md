# Monarch Account Summary

Syncs Monarch Money transactions into our household budget workbook, split by owner (AZS / SSP), with an optional email summary after each sync.

This guide is for setting the app up on your own computer — no coding or Python experience needed.

## 1. Download the code

1. Go to [github.com/gjshao44/monarch-account-summary](https://github.com/gjshao44/monarch-account-summary) and log in with the GitHub/Google account you were given access with.
2. Click the green **Code** button → **Download ZIP**.
3. Extract the ZIP to a folder on your computer (anywhere is fine — e.g. `Documents\monarch-account-summary`).

## 2. Run the installer

1. In the extracted folder, right-click **install.ps1** → **Run with PowerShell**.
2. It installs Python if you don't already have it, sets everything up, and adds a **Monarch Account Summary** shortcut to your Desktop. This takes a few minutes the first time.

If Windows shows a warning like *"running scripts is disabled on this system"* or blocks the file because it came from the internet:
- Right-click `install.ps1` → **Properties** → check the **Unblock** box near the bottom → **OK**, then try again.
- If that doesn't fix it, open PowerShell and run: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.

## 3. Add your private config file

`config\owners.local.yaml` maps real names to the AZS/SSP codes used everywhere else — it's never included in the code (that's intentional, so real names never end up on GitHub). I'll send you this file directly (not through GitHub).

Drop it into the `config` folder inside your extracted project, replacing whatever's there — e.g.:
```
<your extracted folder>\config\owners.local.yaml
```
(If you ran the installer first, it will have already created a placeholder file with fake names at that path — just overwrite it.)

## 4. Add your budget workbook

Put your current `2026 Spending_v2026` workbook into the `expense_data\input` folder (created by the installer, with a note inside as a reminder). Every sync writes a *new* file into `expense_data\output` — your original workbook is never modified.

## 5. Launch the app

Double-click the **Monarch Account Summary** icon on your Desktop. It opens in your web browser (nothing to install in the browser — it's just a local page).

## 6. Enter your Monarch credentials

In the app, open **⚙️ Settings — Monarch credentials** and enter:
- Your Monarch email and password
- (Optional) Your MFA secret key, so syncing doesn't need you to re-enter a code every time — see Monarch's [Multi-Factor Authentication guide](https://help.monarch.com/hc/en-us/articles/360054392152-Multi-Factor-Authentication). This is the raw *secret key*, not a 6-digit code: when you first set up an authenticator app, Monarch shows a QR code plus a "can't scan it? enter this code manually" option — that manual code is what goes here. If you've already set up MFA and don't have that code saved anywhere, you can leave this blank; live sync will just prompt for MFA less conveniently, or you can use the CSV upload option instead (see below).

Credentials are stored securely in Windows' own credential manager on your computer, never in a plain file.

**If live sync doesn't work**, the reliable fallback is: export a transactions CSV yourself from Monarch (Settings → Data → Download Transactions, or the export button on the Transactions/Cash Flow page), then choose "Upload a CSV export" in the app instead of "Fetch live from Monarch."

## 7. (Optional) Enter email alert settings

If you want an email after each sync, open **⚙️ Settings — Email alerts (Gmail)** and enter:
- Your Gmail address
- A Gmail **app password** (a 16-character code, different from your normal Gmail password — Google requires this for apps like this one). Generate one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification to be turned on for your Google account first). See Google's [Sign in with app passwords](https://support.google.com/mail/answer/185833?hl=en) guide if you get stuck.
- Where alerts should be sent (defaults to your own Gmail address if left blank)

Use the **Send test email** button to confirm it's working before your first real sync.

## 8. Sync

Click **🔄 Sync Now**. You'll see spend/income totals per person and combined, a spend-by-month table, and a download button for the synced workbook.

## Troubleshooting

- **"HTTP Code 429: Too Many Requests"** — Monarch is temporarily rate-limiting logins (usually from syncing repeatedly in a short window). Wait a bit and try again.
- **An SSL/certificate error mentioning "Basic Constraints"** — this is your antivirus intercepting HTTPS traffic, not a problem with Monarch or this app. If you use AVG, Avast, Kaspersky, or similar: look for a "Web Shield" or "HTTPS scanning" setting and either disable it temporarily or add an exception for `api.monarch.com`.
- **"Unrecognized Owner value(s)"** — the exact `Owner` name(s) in your Monarch account don't match what's listed in `config\owners.local.yaml` yet. Let me know and I'll help get the config updated.
- **Live fetch not working at all** — switch to "Upload a CSV export" (see step 6) — it's the more reliable, tested path.
