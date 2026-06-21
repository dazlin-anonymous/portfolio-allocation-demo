# Current Project Status

## Completed

- Public demo project separated from the personal dashboard.
- Synthetic holdings replace personal holdings.
- Broker reconciliation removed from the public data model.
- Transactions and CSV-writing UI removed.
- Research assumptions are displayed read-only.
- Public branding and sample-data disclaimer added.
- Yahoo Finance still supplies current prices and 52-week ranges.
- Portfolio Overview displays synthetic owned positions only.
- Position Analysis includes synthetic holdings and watchlist securities.
- DCA Allocation Engine keeps eligibility, quality/moat guardrails, below-cost factor, and fractional/whole-share execution.

## Deployment Target

This project is intended for Streamlit Community Cloud and resume sharing.

Main entry point:

```text
app.py
```

The app uses synthetic sample data only and should not require secrets.

## Important Constraints

- Do not add real holdings or personal broker data.
- Do not add CSV-writing UI in the public demo.
- Keep the public app read-only for resume visitors.
- Keep sample data realistic enough to demonstrate the allocation logic.
