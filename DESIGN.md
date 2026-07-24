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

## Refinements
- **Don't write directly into the master Excel file's formula areas.** Write raw transaction data into a dedicated "Data" tab (or a fresh CSV) that the existing summary formulas already point to. Keeps a bug in the sync script from ever corrupting the summary logic — worst case is bad data, easily fixed.
- **Cash prediction v1**: average monthly spend over last 3 months, plus largest known upcoming bill, plus a buffer %. Can be refined once we see how accurate it is.

## Planned implementation shape
- **Engine**: Python script — pulls Monarch data → writes to Excel Data tab → computes cash-to-keep number → sends email.
- **Front door**: A simple local Streamlit app with buttons like "🔄 Sync Now" and "📧 Send Summary Email" — no terminal or code required day-to-day.
- **Scheduling**: OS task scheduler (Task Scheduler on Windows / cron or launchd on Mac) fires the monthly email automatically; the app itself is used for on-demand syncs.

## Open items / blocked on
- **Excel sheet**: Not yet available — waiting on it from the user's son. Once available, need to inspect:
  - Tab names and layout
  - Which columns/ranges the summary formulas read from
  - Whether a new "Data" tab can be added cleanly, or if the raw-data range needs to match an existing convention
- Once the sheet is in hand, next step is to design the Data tab schema and start building the Monarch connection script.
