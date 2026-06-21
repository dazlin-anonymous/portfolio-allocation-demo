# AGENTS.md

## Project Purpose

This is a public Streamlit portfolio-allocation demo for resume sharing.

The app demonstrates a decision-support workflow for allocating a sample monthly DCA budget across synthetic holdings while considering:

- valuation upside versus sample fair value;
- position in the 52-week range;
- average cost versus current price;
- conviction, moat strength, moat trend, and business quality;
- maximum portfolio-weight limits;
- position type restrictions;
- thesis status;
- fractional-share versus whole-share execution.

This is a demo only. It must not contain real personal holdings and must not automatically place trades.

## Main Files

- `app.py`: Streamlit application, portfolio calculations, DCA scoring, and position analysis.
- `data/holdings.csv`: synthetic open positions.
- `data/security_master.csv`: synthetic research and judgement assumptions for owned and watchlist securities.
- `requirements.txt`: Python dependencies.
- `README.md`: local and Streamlit deployment instructions.

## Data Model

### `data/holdings.csv`

This file represents synthetic owned positions.

Expected fields:

- `Ticker`
- `Quantity`
- `Average_Cost`
- `Currency`

Do not add broker fields to the public demo. The personal dashboard handles broker reconciliation; this public version does not.

### `data/security_master.csv`

This file represents the full synthetic security universe: owned holdings plus watchlist/research securities.

Expected fields:

- `Ticker`
- `Name`
- `Asset_Class`
- `Sector`
- `Country`
- `Theme`
- `Conviction`
- `Fair_Value`
- `Position_Type`
- `Moat_Score`
- `Moat_Trend`
- `Quality_Score`
- `Thesis_Status`
- `Max_Weight`
- `Yahoo_Ticker`

A security that exists in `security_master.csv` but not in `holdings.csv` is watchlist-only. It should appear in Position Analysis and Research Assumptions, but not in Portfolio Overview.

## Public Demo Rules

- Keep the app read-only.
- Do not write to CSV files from the UI.
- Do not add Transactions, Save Changes, or editable Inputs tabs.
- Keep sample data synthetic and resume-safe.
- Use real Yahoo-compatible tickers so live market data still works.
- Keep the visible disclaimer that the data is synthetic and not financial advice.

## Dashboard Behaviour

### Portfolio Overview

Show only securities present in `holdings.csv`.

Include:

- total portfolio value;
- cost basis;
- unrealized P/L;
- unrealized return;
- allocation by ticker;
- holdings table.

### DCA Allocation Engine

The DCA engine considers:

- valuation upside;
- technical discount based on the 52-week range;
- current price versus average cost;
- conviction;
- moat score;
- moat trend;
- quality score;
- current portfolio weight;
- maximum portfolio weight;
- position type;
- thesis status.

Only `Active` securities may receive DCA allocation. Low conviction, zero max weight, max-weight breaches, and non-Active statuses must remain hard stops.

### Position Analysis

Position Analysis should use the full security universe: synthetic holdings and watchlist securities.

Show:

- ticker and company name;
- live price;
- average cost when available;
- fair value;
- valuation upside;
- 52-week range position;
- conviction, moat, quality, thesis status, and weight limits;
- allocation decision;
- supporting factors;
- risks and constraints.

Watchlist securities should show quantity, market value, and current portfolio weight as zero.

### Research Assumptions

Show `security_master.csv` read-only. Do not allow browser edits or saves.

## Testing Expectations

After material changes:

```bash
python3 -m py_compile app.py
python3 -m streamlit run app.py
```

Verify:

- Portfolio Overview loads synthetic holdings only.
- DCA works in fractional mode.
- DCA works in whole-share mode.
- Position Analysis works for eligible, blocked, low-conviction, and watchlist examples.
- Research Assumptions is read-only.
- No broker UI, transaction UI, save button, or CSV-writing path is present.
