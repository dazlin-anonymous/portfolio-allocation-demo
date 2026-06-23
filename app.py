from __future__ import annotations

from pathlib import Path
import math
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

THESIS_STATUS_OPTIONS = [
    "Active",
    "Watchlist",
    "Under Review",
    "Inactive",
    "Broken",
    "Exit Candidate",
]

BLOCKED_THESIS_STATUSES = {
    "watchlist",
    "under review",
    "inactive",
    "broken",
    "exit candidate",
}

POSITION_TYPE_OPTIONS = [
    "Core",
    "Compounder",
    "Value",
    "ETF / Thematic",
    "Speculative",
]

POSITION_TYPE_CAPS = {
    "speculative": 0.05,
    "etf / thematic": 0.15,
    "value": 0.25,
    "compounder": 0.40,
    "core": 1.0,
}

st.set_page_config(
    page_title="Portfolio Allocation Demo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def safe_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def normalize_text(value: object) -> str:
    return str(value or "").strip().lower()


def dca_hard_stop_warnings(row: pd.Series) -> list[str]:
    thesis_status = str(row.get("Thesis_Status", "Not set"))
    normalized_status = normalize_text(thesis_status)
    conviction = safe_float(row.get("Conviction", 0))
    current_weight = safe_float(row.get("Current_Weight", 0))
    max_weight = safe_float(row.get("Max_Weight", 0))

    warnings = []

    if normalized_status in BLOCKED_THESIS_STATUSES or normalized_status != "active":
        warnings.append(
            f"Thesis status is '{thesis_status}', so the position is not currently eligible for DCA."
        )

    if conviction <= 0:
        warnings.append(
            "Conviction is set to 0/10, so the position is not eligible for additional capital."
        )
    elif conviction <= 2:
        warnings.append(
            "Conviction is too low for additional capital under the current rules."
        )

    if max_weight <= 0:
        warnings.append(
            "Maximum portfolio weight is set to 0%, so no additional allocation is allowed."
        )
    elif current_weight >= max_weight:
        warnings.append(
            "Position is already at or above its maximum portfolio weight."
        )

    return warnings


def dca_decision_status(row: pd.Series) -> str:
    if dca_hard_stop_warnings(row):
        return "blocked"
    if safe_float(row.get("Valuation_Upside", 0)) <= 0:
        return "hold"
    return "eligible"


def is_dca_allocation_eligible(row: pd.Series) -> bool:
    return dca_decision_status(row) == "eligible"


def cost_basis_discount(row: pd.Series) -> float:
    average_cost = safe_float(row.get("Average_Cost", 0))
    current_price = safe_float(row.get("Current_Price", 0))

    if average_cost <= 0 or current_price <= 0:
        return 0.0

    return max(0.0, (average_cost - current_price) / average_cost)


def cost_basis_component(row: pd.Series) -> float:
    return min(cost_basis_discount(row), 0.30) / 0.30


def business_quality_guardrail(row: pd.Series) -> tuple[float, list[str]]:
    conviction = safe_float(row.get("Conviction", 0))
    moat_score = safe_float(row.get("Moat_Score", 0))
    quality_score = safe_float(row.get("Quality_Score", 0))
    moat_trend = normalize_text(row.get("Moat_Trend", ""))

    multiplier = 1.0
    warnings = []

    if (moat_score <= 4 or quality_score <= 4) and conviction < 7:
        multiplier = 0.0
        warnings.append(
            "Moat or quality is 4/10 or below, and conviction is below 7/10, so new allocation is blocked."
        )

    if moat_trend == "weakening":
        multiplier *= 0.25
        warnings.append(
            "Moat trend is weakening, so the allocation score is heavily reduced."
        )
    elif moat_trend == "cyclical":
        multiplier *= 0.75
        warnings.append(
            "Moat trend is cyclical, so the allocation score is moderately reduced."
        )

    return multiplier, warnings


def business_quality_multiplier(row: pd.Series) -> float:
    multiplier, _ = business_quality_guardrail(row)
    return multiplier


def business_quality_guardrail_warnings(row: pd.Series) -> list[str]:
    _, warnings = business_quality_guardrail(row)
    return warnings

@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_data(yahoo_tickers: tuple[str, ...]) -> pd.DataFrame:
    records = []
    for ticker in yahoo_tickers:
        try:
            obj = yf.Ticker(ticker)
            hist = obj.history(period="1y", auto_adjust=False)
            if hist.empty:
                raise ValueError("No market history returned")
            close = hist["Close"].dropna()
            high = hist["High"].dropna()
            low = hist["Low"].dropna()
            records.append({
                "Yahoo_Ticker": ticker,
                "Current_Price": float(close.iloc[-1]),
                "Week_52_High": float(high.max()),
                "Week_52_Low": float(low.min()),
                "Market_Data_Status": "Live",
            })
        except Exception as exc:
            records.append({
                "Yahoo_Ticker": ticker,
                "Current_Price": math.nan,
                "Week_52_High": math.nan,
                "Week_52_Low": math.nan,
                "Market_Data_Status": f"Unavailable: {exc}",
            })
    return pd.DataFrame(records)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    holdings = pd.read_csv(DATA_DIR / "holdings.csv")
    master = pd.read_csv(DATA_DIR / "security_master.csv")
    numeric_holdings = ["Quantity", "Average_Cost"]
    numeric_master = ["Conviction", "Fair_Value", "Moat_Score", "Quality_Score", "Max_Weight"]
    for col in numeric_holdings:
        holdings[col] = pd.to_numeric(holdings[col], errors="coerce").fillna(0)
    for col in numeric_master:
        master[col] = pd.to_numeric(master[col], errors="coerce")
    return holdings, master

def build_security_universe(
    master: pd.DataFrame,
    market: pd.DataFrame,
    portfolio: pd.DataFrame,
) -> pd.DataFrame:
    universe = master.copy()

    universe = universe.merge(
        market,
        on="Yahoo_Ticker",
        how="left",
    )

    holding_columns = [
        "Ticker",
        "Quantity",
        "Average_Cost",
        "Cost_Basis",
        "Market_Value",
        "Current_Weight",
        "Unrealized_PL",
        "Unrealized_Return",
    ]

    available_holding_columns = [
        col for col in holding_columns
        if col in portfolio.columns
    ]

    universe = universe.merge(
        portfolio[available_holding_columns],
        on="Ticker",
        how="left",
        suffixes=("", "_Holding"),
    )

    numeric_defaults = [
        "Quantity",
        "Average_Cost",
        "Cost_Basis",
        "Market_Value",
        "Current_Weight",
        "Unrealized_PL",
        "Unrealized_Return",
    ]

    for col in numeric_defaults:
        if col in universe.columns:
            universe[col] = universe[col].fillna(0)

    universe["Valuation_Upside"] = (
        universe["Fair_Value"] - universe["Current_Price"]
    ) / universe["Current_Price"]

    range_width = (
        universe["Week_52_High"] - universe["Week_52_Low"]
    ).replace(0, pd.NA)

    universe["Position_In_52W_Range"] = (
        universe["Current_Price"] - universe["Week_52_Low"]
    ) / range_width

    return universe

def consolidate(holdings: pd.DataFrame, master: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    holdings = holdings.copy()
    holdings["Cost_Basis"] = holdings["Quantity"] * holdings["Average_Cost"]
    grouped = holdings.groupby("Ticker", as_index=False).agg(
        Quantity=("Quantity", "sum"),
        Cost_Basis=("Cost_Basis", "sum"),
    )
    grouped["Average_Cost"] = grouped["Cost_Basis"] / grouped["Quantity"].replace(0, pd.NA)
    df = grouped.merge(master, on="Ticker", how="left").merge(market, on="Yahoo_Ticker", how="left")
    df["Market_Value"] = df["Quantity"] * df["Current_Price"]
    df["Unrealized_PL"] = df["Market_Value"] - df["Cost_Basis"]
    df["Unrealized_Return"] = df["Unrealized_PL"] / df["Cost_Basis"].replace(0, pd.NA)
    total = df["Market_Value"].sum()
    df["Current_Weight"] = df["Market_Value"] / total if total else 0
    df["Valuation_Upside"] = (df["Fair_Value"] - df["Current_Price"]) / df["Current_Price"]
    range_width = (df["Week_52_High"] - df["Week_52_Low"]).replace(0, pd.NA)
    df["Position_In_52W_Range"] = (df["Current_Price"] - df["Week_52_Low"]) / range_width
    df["Technical_Discount"] = (1 - df["Position_In_52W_Range"]).clip(0, 1)
    return df


def moat_trend_score(value: str) -> float:
    return {"Strengthening": 1.0, "Stable": 0.7, "Unclear": 0.4, "Weakening": 0.0}.get(str(value), 0.4)


def position_type_cap(position_type: str) -> float:
    return POSITION_TYPE_CAPS.get(normalize_text(position_type), 0.20)


def build_dca_recommendation(df: pd.DataFrame, budget: float) -> pd.DataFrame:
    scored = df.copy()
    scored["Valuation_Component"] = scored["Valuation_Upside"].clip(lower=-0.25, upper=0.60).add(0.25).div(0.85).clip(0, 1)
    scored["Technical_Component"] = scored["Technical_Discount"].fillna(0.5).clip(0, 1)
    scored["Conviction_Component"] = (scored["Conviction"] / 10).clip(0, 1)
    scored["Moat_Component"] = (scored["Moat_Score"] / 10).clip(0, 1)
    scored["Moat_Trend_Component"] = scored["Moat_Trend"].map(moat_trend_score)
    scored["Quality_Component"] = (scored["Quality_Score"] / 10).clip(0, 1)
    scored["Cost_Basis_Discount"] = scored.apply(cost_basis_discount, axis=1)
    scored["Cost_Basis_Component"] = scored.apply(cost_basis_component, axis=1)

    scored["Base_Score"] = (
        0.25 * scored["Valuation_Component"]
        + 0.12 * scored["Technical_Component"]
        + 0.20 * scored["Conviction_Component"]
        + 0.12 * scored["Moat_Component"]
        + 0.08 * scored["Moat_Trend_Component"]
        + 0.15 * scored["Quality_Component"]
        + 0.08 * scored["Cost_Basis_Component"]
    )
    scored["Headroom"] = (scored["Max_Weight"] - scored["Current_Weight"]).clip(lower=0)
    scored["Concentration_Multiplier"] = (scored["Headroom"] / scored["Max_Weight"].replace(0, pd.NA)).fillna(0).clip(0, 1)
    scored["Adjusted_Score"] = scored["Base_Score"] * (0.25 + 0.75 * scored["Concentration_Multiplier"])

    eligible_for_allocation = scored.apply(is_dca_allocation_eligible, axis=1)
    scored.loc[~eligible_for_allocation, "Adjusted_Score"] = 0.0
    scored["Business_Quality_Multiplier"] = scored.apply(
        business_quality_multiplier,
        axis=1,
    )
    scored["Adjusted_Score"] *= scored["Business_Quality_Multiplier"]
    scored.loc[scored["Valuation_Upside"] < -0.10, "Adjusted_Score"] *= 0.25

    raw_total = scored["Adjusted_Score"].sum()
    scored["Suggested_Allocation"] = budget * scored["Adjusted_Score"] / raw_total if raw_total > 0 else 0

    # Per-month caps based on conviction and position type.
    conviction_cap = scored["Conviction"].apply(lambda x: 0.05 if x < 3 else (0.10 if x < 5 else (0.25 if x < 7 else 1.0)))
    type_cap = scored["Position_Type"].map(position_type_cap)
    monthly_cap = pd.concat([conviction_cap, type_cap], axis=1).min(axis=1) * budget
    position_room_dollars = (scored["Max_Weight"] * (scored["Market_Value"].sum() + budget) - scored["Market_Value"]).clip(lower=0)
    scored["Suggested_Allocation"] = scored["Suggested_Allocation"].clip(upper=monthly_cap)
    scored["Suggested_Allocation"] = scored[["Suggested_Allocation"]].join(position_room_dollars.rename("room"), how="left").min(axis=1)

    # Redistribute unused budget while respecting caps.
    for _ in range(20):
        unused = budget - scored["Suggested_Allocation"].sum()
        if unused <= 0.01:
            break
        remaining_cap = pd.concat([monthly_cap, position_room_dollars], axis=1).min(axis=1) - scored["Suggested_Allocation"]
        eligible = (remaining_cap > 0.01) & (scored["Adjusted_Score"] > 0)
        if not eligible.any():
            break
        weights = scored.loc[eligible, "Adjusted_Score"]
        additions = unused * weights / weights.sum()
        additions = additions.clip(upper=remaining_cap.loc[eligible])
        scored.loc[eligible, "Suggested_Allocation"] += additions

    scored["Suggested_Allocation"] = scored["Suggested_Allocation"].round(2)
    scored["Post_DCA_Weight"] = (scored["Market_Value"] + scored["Suggested_Allocation"]) / (scored["Market_Value"].sum() + scored["Suggested_Allocation"].sum())
    return scored.sort_values(["Suggested_Allocation", "Adjusted_Score"], ascending=False)

st.title("📊 Portfolio Allocation Demo Dashboard")
st.caption(
    "This public demo uses synthetic sample holdings and research assumptions. "
    "It is not financial advice and does not represent real personal holdings. "
    "Prices and 52-week ranges refresh from Yahoo Finance."
)
st.caption("Built by Dazlin · Python, Streamlit, Pandas, Plotly, Yahoo Finance")

holdings, master = load_inputs()
if st.button("Refresh market data"):
    fetch_market_data.clear()
market = fetch_market_data(tuple(master["Yahoo_Ticker"].dropna().astype(str).unique()))
portfolio = consolidate(holdings, master, market)
security_universe = build_security_universe(
    master,
    market,
    portfolio,
)

missing = portfolio[portfolio["Current_Price"].isna()]
if not missing.empty:
    st.warning("Market data could not be retrieved for: " + ", ".join(missing["Ticker"].tolist()))

overview_tab, dca_tab, analysis_tab, research_tab = st.tabs(
    [
        "Portfolio Overview",
        "DCA Allocation Engine",
        "Position Analysis",
        "Research Assumptions",
    ]
)

with overview_tab:
    total_value = portfolio["Market_Value"].sum()
    total_cost = portfolio["Cost_Basis"].sum()
    total_pl = total_value - total_cost
    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio value", f"${total_value:,.2f}")
    c2.metric("Cost basis", f"${total_cost:,.2f}")
    c3.metric("Unrealized P/L", f"${total_pl:,.2f}", f"{total_pl / total_cost:.1%}" if total_cost else None)

    chart_col, table_col = st.columns([1, 1.6])
    with chart_col:
        fig = px.pie(portfolio, values="Market_Value", names="Ticker", title="Allocation by ticker", hole=0.45)
        st.plotly_chart(fig, use_container_width=True)
    with table_col:
        display = portfolio[["Ticker", "Quantity", "Average_Cost", "Current_Price", "Market_Value", "Current_Weight", "Unrealized_PL", "Unrealized_Return"]].copy()
        st.dataframe(display.style.format({
            "Quantity": "{:,.4f}", "Average_Cost": "${:,.2f}", "Current_Price": "${:,.2f}", "Market_Value": "${:,.2f}",
            "Current_Weight": "{:.1%}", "Unrealized_PL": "${:,.2f}", "Unrealized_Return": "{:.1%}"
        }), use_container_width=True, hide_index=True)

with dca_tab:
    st.subheader("Monthly DCA recommendation")

    budget = st.number_input(
        "Capital available (USD)",
        min_value=0.0,
        value=1000.0,
        step=100.0,
    )

    execution_mode = st.radio(
        "Execution mode",
        [
            "Fractional shares",
            "Whole shares only",
        ],
        horizontal=True,
    )

    fractional_allowed = execution_mode == "Fractional shares"
    rec = build_dca_recommendation(portfolio, budget)

    if fractional_allowed:
        rec["Shares_To_Buy"] = (
            rec["Suggested_Allocation"] / rec["Current_Price"]
        ).fillna(0)
        rec["Executable_Amount"] = rec["Suggested_Allocation"]
        rec["Unallocated_Due_To_Rounding"] = 0.0

    else:
        rec["Shares_To_Buy"] = (
            rec["Suggested_Allocation"] / rec["Current_Price"]
        ).fillna(0).apply(math.floor)

        rec["Executable_Amount"] = (
            rec["Shares_To_Buy"] * rec["Current_Price"]
        )

        rec["Unallocated_Due_To_Rounding"] = (
            rec["Suggested_Allocation"] - rec["Executable_Amount"]
        ).clip(lower=0)
    allocated = rec["Executable_Amount"].sum()
    cash = max(0.0, budget - allocated)
    post_dca_total = rec["Market_Value"].sum() + allocated
    rec["Post_DCA_Weight"] = (
        (rec["Market_Value"] + rec["Executable_Amount"]) / post_dca_total
        if post_dca_total
        else 0
    )
    a1, a2 = st.columns(2)
    a1.metric("Recommended purchases", f"${allocated:,.2f}")
    a2.metric("Remain as cash", f"${cash:,.2f}")
    rec_display = rec[
        [
            "Ticker",
            "Position_Type",
            "Conviction",
            "Current_Weight",
            "Max_Weight",
            "Average_Cost",
            "Current_Price",
            "Cost_Basis_Discount",
            "Valuation_Upside",
            "Position_In_52W_Range",
            "Moat_Score",
            "Moat_Trend",
            "Quality_Score",
            "Cost_Basis_Component",
            "Business_Quality_Multiplier",
            "Adjusted_Score",
            "Suggested_Allocation",
            "Shares_To_Buy",
            "Executable_Amount",
            "Unallocated_Due_To_Rounding",
            "Post_DCA_Weight",
        ]
    ]
    st.dataframe(rec_display.style.format({
        "Current_Weight": "{:.1%}",
        "Max_Weight": "{:.1%}",
        "Average_Cost": "${:,.2f}",
        "Current_Price": "${:,.2f}",
        "Cost_Basis_Discount": "{:.1%}",
        "Valuation_Upside": "{:.1%}",
        "Position_In_52W_Range": "{:.1%}",
        "Cost_Basis_Component": "{:.3f}",
        "Business_Quality_Multiplier": "{:.2f}",
        "Adjusted_Score": "{:.3f}",
        "Suggested_Allocation": "${:,.2f}",
        "Shares_To_Buy": "{:,.4f}" if fractional_allowed else "{:,.0f}",
        "Executable_Amount": "${:,.2f}",
        "Unallocated_Due_To_Rounding": "${:,.2f}",
        "Post_DCA_Weight": "{:.1%}",
    }), use_container_width=True, hide_index=True)
    st.info("The recommendation is decision support, not an automatic trade instruction. Review fair values, thesis changes, position-specific risks, and upcoming market events before placing orders.")

with analysis_tab:
    st.subheader("Position Analysis")

    chosen = st.selectbox(
        "Select a security",
        security_universe["Ticker"]
        .dropna()
        .astype(str)
        .sort_values()
        .tolist()
    )

    row = security_universe.loc[
        security_universe["Ticker"].eq(chosen)
    ].iloc[0]

    live_price = safe_float(row.get("Current_Price", 0))
    fair_value = safe_float(row.get("Fair_Value", 0))
    average_cost = safe_float(row.get("Average_Cost", 0))
    week_52_low = safe_float(row.get("Week_52_Low", 0))
    week_52_high = safe_float(row.get("Week_52_High", 0))
    cost_discount = cost_basis_discount(row)

    valuation_upside = (
        (fair_value - live_price) / live_price
        if live_price > 0 and fair_value > 0
        else 0
    )

    if week_52_high > week_52_low:
        range_position = (
            (live_price - week_52_low)
            / (week_52_high - week_52_low)
        )
        range_position = max(0, min(range_position, 1))
    else:
        range_position = 0

    conviction = int(safe_float(row.get("Conviction", 0)))
    moat_score = int(safe_float(row.get("Moat_Score", 0)))
    quality_score = int(safe_float(row.get("Quality_Score", 0)))

    position_type = str(row.get("Position_Type", "Not set"))
    asset_class = str(row.get("Asset_Class", "")).strip()
    moat_trend = str(row.get("Moat_Trend", "Not set"))
    thesis_status = str(row.get("Thesis_Status", "Not set"))

    is_etf = asset_class.lower() == "etf"
    subject_label = "fund" if is_etf else "company"
    moat_label = "Exposure score" if is_etf else "Moat score"
    moat_trend_label = "Exposure trend" if is_etf else "Moat trend"
    quality_label = "Exposure quality" if is_etf else "Business quality"

    current_weight = safe_float(row.get("Current_Weight", 0))
    max_weight = safe_float(row.get("Max_Weight", 0))

    reasons = []
    warnings = dca_hard_stop_warnings(row)
    warnings.extend(business_quality_guardrail_warnings(row))

    if 2 < conviction <= 3:
        warnings.append(
            "Conviction is low, so any additional allocation should remain small."
        )
    

    if valuation_upside > 0.20:
        reasons.append(
            f"The {subject_label} trades materially below your fair-value estimate."
        )
    elif valuation_upside > 0:
        reasons.append(
            f"The {subject_label} trades below your fair-value estimate."
        )
    else:
        warnings.append(
            f"The {subject_label} trades at or above your fair-value estimate."
        )

    if average_cost > 0 and live_price > 0:
        if cost_discount > 0:
            reasons.append(
                "The current price is below your average cost, so new capital would reduce your blended cost basis."
            )
        else:
            warnings.append(
                "The current price is above your average cost, so this is not a cost-basis averaging opportunity."
            )

    if range_position <= 0.25:
        reasons.append(
            "The price is in the lower quarter of its 52-week range."
        )
    elif range_position >= 0.75:
        warnings.append(
            "The price is near the upper end of its 52-week range."
        )

    if moat_score >= 8:
        if is_etf:
            reasons.append(
                "The ETF has attractive structural exposure."
            )
        else:
            reasons.append(
                "The company has a strong competitive moat."
            )
    elif moat_score <= 4:
        if is_etf:
            warnings.append(
                "The ETF exposure appears limited or uncertain."
            )
        else:
            warnings.append(
                "The competitive moat appears limited or uncertain."
            )

    if quality_score >= 8:
        reasons.append(
            f"{quality_label} is rated highly."
        )
    elif quality_score <= 4:
        warnings.append(
            f"{quality_label} is rated relatively low."
        )

    if moat_trend.lower() == "weakening":
        if is_etf:
            warnings.append(
                "The ETF exposure trend is marked as weakening."
            )
        else:
            warnings.append(
                "The competitive moat is marked as weakening."
            )
    elif moat_trend.lower() == "strengthening":
        if is_etf:
            reasons.append(
                "The ETF exposure trend appears to be improving."
            )
        else:
            reasons.append(
                "The competitive moat appears to be strengthening."
            )
    
    decision_status = dca_decision_status(row)

    company_name = str(row.get("Name", ""))

    st.markdown(f"## {chosen}")

    if company_name:
        st.markdown(
            f"<div style='font-size:18px; color:#6b7280; margin-top:-12px; margin-bottom:18px;'>"
            f"{company_name}"
            f"</div>",
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Live price",
        f"${live_price:,.2f}",
        f"{cost_discount:.1%} below cost"
        if average_cost > 0 and live_price > 0 and cost_discount > 0
        else None,
    )
    c2.metric(
        "Average cost",
        f"${average_cost:,.2f}" if average_cost > 0 else "N/A",
    )
    c3.metric(
        "Fair value",
        f"${fair_value:,.2f}",
        f"{valuation_upside:.1%} upside",
    )
    c4.metric("52-week position", f"{range_position:.1%}")

    st.divider()

    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("### Investment profile")

        profile_df = pd.DataFrame({
            "Factor": [
                "Position type",
                "Conviction",
                moat_label,
                moat_trend_label,
                quality_label,
                "Thesis status",
                "Current weight",
                "Maximum weight",
            ],
            "Assessment": [
                position_type,
                f"{conviction}/10",
                f"{moat_score}/10",
                moat_trend,
                f"{quality_score}/10",
                thesis_status,
                f"{current_weight:.1%}",
                f"{max_weight:.1%}",
            ],
        })

        st.dataframe(
            profile_df,
            hide_index=True,
            use_container_width=True
        )

    with right:
        st.markdown("### Allocation decision")

        if decision_status == "eligible":
            st.success("**Eligible for DCA**")
            st.write(
                "This position is below your fair-value estimate and remains "
                "within its portfolio constraints."
            )

        elif decision_status == "hold":
            st.warning("**Hold / Wait**")
            if is_etf:
                st.write(
                    "The fund exposure remains acceptable, but the current price is "
                    "at or above your fair-value estimate. Wait for a better entry."
                )
            else:
                st.write(
                    "The business remains acceptable, but the current price is "
                    "at or above your fair-value estimate. Wait for a better entry."
                )

        else:
            st.error("**Do not add**")
            st.write(
                "The current rules do not support adding more capital "
                "to this position."
            )

        remaining_capacity = max(0, max_weight - current_weight)

        st.metric(
            "Remaining weight capacity",
            f"{remaining_capacity:.1%}"
        )

        progress_value = (
            min(current_weight / max_weight, 1.0)
            if max_weight > 0
            else 0
        )

        st.progress(progress_value)

        st.caption(
            f"Current weight: {current_weight:.1%} "
            f"of a {max_weight:.1%} maximum."
        )

    st.divider()

    reason_col, warning_col = st.columns(2)

    with reason_col:
        st.markdown("### Supporting factors")

        if reasons:
            for reason in reasons:
                st.write(f"✓ {reason}")
        else:
            st.write("No major positive factors identified.")

    with warning_col:
        st.markdown("### Risks and constraints")

        if warnings:
            for warning in warnings:
                st.write(f"⚠ {warning}")
        else:
            st.write("No major constraints identified.")

    st.divider()

    st.markdown("### Market context")

    market_df = pd.DataFrame({
        "Metric": [
            "52-week low",
            "Current price",
            "52-week high",
            "Market data status",
        ],
        "Value": [
            f"${week_52_low:,.2f}",
            f"${live_price:,.2f}",
            f"${week_52_high:,.2f}",
            str(row.get("Market_Data_Status", "Live")),
        ],
    })

    st.dataframe(
        market_df,
        hide_index=True,
        use_container_width=True
    )

with research_tab:
    st.subheader("Research Assumptions")

    st.caption(
        "Read-only sample assumptions used by this public demo. "
        "Fair values, conviction, moat, quality, thesis status, and max weights are synthetic."
    )

    research_columns = [
        "Ticker",
        "Name",
        "Asset_Class",
        "Sector",
        "Theme",
        "Fair_Value",
        "Conviction",
        "Position_Type",
        "Moat_Score",
        "Moat_Trend",
        "Quality_Score",
        "Thesis_Status",
        "Max_Weight",
        "Yahoo_Ticker",
    ]

    research_display = master[research_columns].copy()

    st.dataframe(
        research_display.style.format({
            "Fair_Value": "${:,.2f}",
            "Max_Weight": "{:.1%}",
        }),
        use_container_width=True,
        hide_index=True,
    )
