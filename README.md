# Portfolio Allocation Demo Dashboard

This is a public Streamlit demo of a portfolio allocation dashboard.

The app uses synthetic sample holdings and research assumptions. It does not contain real personal holdings and is not financial advice.

## Features

- Live prices and 52-week ranges from Yahoo Finance.
- Portfolio overview for synthetic holdings.
- Monthly DCA allocation engine.
- Fractional-share and whole-share execution modes.
- Position analysis with valuation, 52-week range, cost basis, conviction, moat, quality, and concentration rules.
- Read-only research assumptions table.

## Streamlit Community Cloud

Use these settings when deploying:

- Repository: this project repository
- Branch: your deployment branch
- Main file path: `app.py`
- Python dependencies: `requirements.txt`

No secrets are required.

## Run Locally

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Data Files

- `data/holdings.csv`: synthetic ticker, quantity, average cost, and currency.
- `data/security_master.csv`: synthetic research assumptions and Yahoo tickers.

The public app is read-only and does not write back to these CSV files.
