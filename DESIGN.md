# Monarch Account Summary — Design Notes

## Goal
An easy-to-use (non-technical-friendly) app that:
1. Connects to Monarch Money and downloads transaction data.
2. Feeds that data into an existing Excel sheet (which already has summary rules/formulas).
3. Predicts how much cash to keep on hand.
4. Auto-categorizes transactions based on rules.
5. Emails a summary monthly or on demand.

## Feasibility

| Requirement | Doable? | Notes |
|---|---|---|
| Connect to Monarch | Yes, with a caveat | No official public API. Plan is to use the well-maintained unofficial Python client `monarchmoney`, which logs in (handles MFA) and pulls accounts/transactions/budgets. Risk: if Monarch changes their site, the library can break until updated. |
| Feed data into Excel | Yes | Write into the workbook via `openpyxl`, targeting a dedicated tab/range so it plugs into existing formulas. |
| Cash-to-keep prediction | Yes, as a heuristic | Not ML — a smart formula (e.g. rolling average of expenses + known upcoming bills + buffer). Explainable and reliable, start simple and tune later. |
| Auto-categorization | Yes | Monarch already auto-categorizes transactions. Plan: use Monarch's own categories directly rather than building a custom rule engine. Custom keyword-override rules can be added later if needed. |
| Monthly/on-demand email | Yes | Send via Gmail (app password) + scheduled trigger for monthly, plus a manual "send now" option. |

## Decisions made so far
- **Hosting**: Runs locally on the user's own computer (no cloud hosting/secrets management needed). Scheduled monthly email requires the computer to be on at that time.
- **Email provider**: Gmail (via app password).
- **Categorization**: Use Monarch's own categories as-is for v1. No custom rule engine initially — can add simple keyword-override rules later if Monarch's categorization needs correction.
- **Multi-user household**: the Monarch account covers two people, referred to everywhere in code/docs only as `AZS` and `SSP` (matching the abbreviations already used in the workbook's sheet names). Output is combined (both people summed) plus a separate breakdown per person — never one undifferentiated pile. Real names are never written into the repo: the real-name↔code mapping lives in a local, gitignored `config/owners.local.yaml` (see `config/owners.example.yaml` for the template); `expense_data/` (raw exports, synced workbooks) is entirely gitignored too.
- **Key metrics**: monthly spending (combined + per-person) and **% Gross Savings** / **% Net Savings** (combined + per-person) are the metrics that matter most and must always be present in the output.
- **Shared expenses**: a transaction Monarch has no single owner for (`Owner = Shared`) is split 50/50 between AZS and SSP by default (configurable ratio in `owners.local.yaml`).
- **Secret storage**: Monarch (and, later, Gmail) credentials are never stored in a plaintext file or env var. They're stored via `keyring` in the OS-native credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service), entered once through the Streamlit app's Settings section. The app is intended to run as **native Windows Python** day-to-day (not WSL), so this resolves to Windows Credential Manager automatically with no extra setup.

## Refinements
- **Don't write directly into the master Excel file's formula areas.** Write raw transaction data into a dedicated "Data" tab (or a fresh CSV) that the existing summary formulas already point to. Keeps a bug in the sync script from ever corrupting the summary logic — worst case is bad data, easily fixed.
- **Cash prediction v1**: average monthly spend over last 3 months, plus largest known upcoming bill, plus a buffer %. Can be refined once we see how accurate it is.

## Planned implementation shape
- **Engine**: Python script — pulls Monarch data → writes to Excel Data tab → computes cash-to-keep number → sends email.
- **Front door**: A simple local Streamlit app with buttons like "🔄 Sync Now" and "📧 Send Summary Email" — no terminal or code required day-to-day.
- **Scheduling**: OS task scheduler (Task Scheduler on Windows / cron or launchd on Mac) fires the monthly email automatically; the app itself is used for on-demand syncs.

## Status
- **Excel sheet**: in hand. It already has `Data_AZS`/`Data_SSP` raw-data tabs (`Mo, Date, Account, Description, Amount ($), Label, Notes`, data starting row 6) and `Monthly_AZS` / `Monthly_SSP` / `Monthy_Comb` tabs that already compute spending-per-month and % Net/Gross Savings from those tabs via formulas — this is the "combined + per-person" output surface. **Gross Income is a manual-entry cell** in the template (`Monthly_AZS!E5` / `Monthly_SSP!E5`, no formula) since gross salary isn't derivable from bank deposits — fill it in once per person for Gross Savings % to be meaningful.
- **v1 built**: a tested Python CLI (`src/monarch_summary/`, `monarch-summary sync --transactions <csv> --workbook <xlsx>`) parses a Monarch CSV export, routes rows to AZS/SSP (splitting `Shared` 50/50), maps Monarch categories to the workbook's Label taxonomy (`config/categories.yaml`), and writes into a copy of the workbook's `Data_AZS`/`Data_SSP` tabs — leaving every formula/other sheet untouched. Verified end-to-end against sample data; unit-tested with synthetic fixtures (`tests/`, no real data).
- **Live Monarch connection** (`monarch_client.py`): implemented against the `monarchmoney` package's login/`get_transactions` API, but **unverified** — no test credentials available yet. It feeds the same tested pipeline (owner routing → category mapping → Excel write), so the only unverified surface is the auth+fetch call itself and its exact response shape. One known open question: it's unconfirmed whether the live API exposes a per-transaction "Owner" the way the CSV export does, or whether owner has to be inferred from the account instead — needs checking against a real account.
- **Streamlit front door**: v1 built (`app.py`, `streamlit run app.py`). A Settings section for entering/clearing Monarch credentials (stored via `keyring`, see above) and a Sync section with a "🔄 Sync Now" button — either upload a CSV export (tested path) or fetch live from Monarch using the stored credentials (uses the still-unverified `monarch_client.py`). Shows combined + per-AZS/SSP spend and monthly breakdown, unmapped-category warnings, and the Gross-Income-is-manual-entry reminder, plus a download button for the synced workbook. The sync logic itself lives in `src/monarch_summary/pipeline.py`, shared by both the CLI and the app so they can't drift apart. Boot-tested (server starts, page serves, no exceptions in logs) but the interactive paths (button clicks, credential save/clear, live fetch) haven't been click-tested in a real browser yet — do that once running natively on Windows.
- **Cash-to-keep prediction and scheduled email**: not started, still later phases. Gmail credentials will reuse the same `keyring`-based `credentials.py` module when that phase starts.
