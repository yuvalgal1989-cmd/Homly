#!/usr/bin/env python3
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

from mortgage import simulate_mortgage_scenarios, calculate_cash_flow

OUT_DIR = Path("./yad2_output")
YIELD_FORMAT = "{:.2%}"

st.set_page_config(
    page_title="Homly",
    page_icon="🏠",
    layout="wide",
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


def clean_address(addr: str) -> str:
    """Strip agency name prefix (format: 'Agency | Street')."""
    if isinstance(addr, str) and "|" in addr:
        return addr.split("|", 1)[1].strip()
    return addr if isinstance(addr, str) else ""


def fmt_num(val, prefix="₪"):
    if pd.isna(val):
        return "—"
    return f"{prefix}{round(float(val), 1):,.1f}"


def fmt_price(val):
    return fmt_num(val, prefix="₪")


def fmt_ppsqm(val):
    return fmt_num(val, prefix="₪")


def fmt_yield(val):
    if pd.isna(val):
        return "—"
    return f"{round(float(val) * 100, 1):.1f}%"


def fmt_rooms(val):
    if pd.isna(val):
        return "—"
    return f"{round(float(val), 1):.1f}"


# Thresholds above which a value is flagged as suspicious
SUSPICIOUS = {
    "rent_price":        30_000,   # monthly rent > 30k is likely a parse error
    "rent_price_per_sqm": 500,     # ₪/m²/month > 500 doesn't make sense
    "gross_yield":         0.15,   # > 15% gross yield is unrealistic
}

RED_BG   = "background-color: #FF4B4B; color: white;"
CLEAR_BG = ""


def flag_rent_price(val):
    try:
        return RED_BG if float(val) > SUSPICIOUS["rent_price"] else CLEAR_BG
    except (TypeError, ValueError):
        return CLEAR_BG


def flag_rent_ppsqm(val):
    try:
        return RED_BG if float(val) > SUSPICIOUS["rent_price_per_sqm"] else CLEAR_BG
    except (TypeError, ValueError):
        return CLEAR_BG


def flag_yield(val):
    try:
        return RED_BG if float(val) > SUSPICIOUS["gross_yield"] else CLEAR_BG
    except (TypeError, ValueError):
        return CLEAR_BG


def available_folders() -> list[str]:
    if not OUT_DIR.exists():
        return []
    return sorted([d.name for d in OUT_DIR.iterdir() if d.is_dir()])


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("🏠 Homly")

folders = available_folders()
if not folders:
    st.error(f"No data found in `{OUT_DIR.resolve()}`. Run the scraper first.")
    st.stop()

selected = st.sidebar.selectbox("Search area", folders)
folder = OUT_DIR / selected

sale_df   = load_csv(folder / "sale_raw_listings.csv")
rent_df   = load_csv(folder / "rent_raw_listings.csv")
sale_sum  = load_csv(folder / "sale_summary_by_rooms.csv")
rent_sum  = load_csv(folder / "rent_summary_by_rooms.csv")
comp_df   = load_csv(folder / "buy_rent_comparison.csv")
yield_df  = load_csv(folder / "sale_listing_yield_estimates.csv")

# Clean addresses
for df in [sale_df, rent_df, yield_df]:
    if "address" in df.columns:
        df["address"] = df["address"].apply(clean_address)

st.sidebar.markdown("---")
st.sidebar.metric("Sale listings", len(sale_df))
st.sidebar.metric("Rent listings", len(rent_df))

# ── Tabs ────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Listings",
    "📊 Market Stats",
    "⚖️ Buy vs Rent",
    "💰 Yield Estimates",
    "🏦 Mortgage Calculator",
])


# ────────────────────────────────────────────────────────────────────────────────
# TAB 1 — RAW LISTINGS
# ────────────────────────────────────────────────────────────────────────────────

with tab1:
    st.header(f"Listings — {selected.replace('_', ' ')}")

    col_sale, col_rent = st.columns(2)

    with col_sale:
        st.subheader("For Sale")
        if sale_df.empty:
            st.info("No sale data.")
        else:
            rooms_opts = sorted(sale_df["rooms"].dropna().unique().tolist())
            sel_rooms = st.multiselect("Filter by rooms (sale)", rooms_opts, key="sale_rooms")
            df = sale_df[sale_df["rooms"].isin(sel_rooms)] if sel_rooms else sale_df

            display = df[["address", "rooms", "size_sqm", "floor", "price", "price_per_sqm", "link"]].copy()
            display["price"] = display["price"].apply(fmt_price)
            display["rooms"] = display["rooms"].apply(fmt_rooms)
            display["price_per_sqm"] = display["price_per_sqm"].apply(fmt_ppsqm)
            display.columns = ["Address", "Rooms", "Size (m²)", "Floor", "Price", "₪/m²", "Link"]
            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open ↗")},
            )

    with col_rent:
        st.subheader("For Rent")
        if rent_df.empty:
            st.info("No rent data.")
        else:
            rooms_opts = sorted(rent_df["rooms"].dropna().unique().tolist())
            sel_rooms = st.multiselect("Filter by rooms (rent)", rooms_opts, key="rent_rooms")
            df = rent_df[rent_df["rooms"].isin(sel_rooms)] if sel_rooms else rent_df

            display = df[["address", "rooms", "size_sqm", "floor", "price", "price_per_sqm", "link"]].copy()
            display = display.rename(columns={
                "address": "Address", "rooms": "Rooms", "size_sqm": "Size (m²)",
                "floor": "Floor", "price": "Rent/mo", "price_per_sqm": "₪/m²", "link": "Link",
            })
            styled = display.style \
                .applymap(flag_rent_price, subset=["Rent/mo"]) \
                .applymap(flag_rent_ppsqm, subset=["₪/m²"]) \
                .format({
                    "Rooms":   fmt_rooms,
                    "Rent/mo": fmt_price,
                    "₪/m²":    fmt_ppsqm,
                })
            st.dataframe(
                styled,
                use_container_width=True,
                hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open ↗")},
            )


# ────────────────────────────────────────────────────────────────────────────────
# TAB 2 — MARKET STATS
# ────────────────────────────────────────────────────────────────────────────────

with tab2:
    st.header("Market Statistics")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Sale — Avg Price by Rooms")
        if not sale_sum.empty:
            fig = px.bar(
                sale_sum,
                x="rooms",
                y="avg_sale_price",
                error_y=None,
                labels={"rooms": "Rooms", "avg_sale_price": "Avg Price (₪)"},
                text="avg_sale_price",
                color_discrete_sequence=["#4C78A8"],
            )
            fig.update_traces(texttemplate="₪%{text:,.1f}", textposition="outside")
            fig.update_layout(showlegend=False, yaxis_tickformat=",.1f")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                sale_sum.rename(columns={
                    "rooms": "Rooms",
                    "avg_sale_price": "Avg (₪)",
                    "min_sale_price": "Min (₪)",
                    "max_sale_price": "Max (₪)",
                    "median_sale_price": "Median (₪)",
                    "count_sale": "Count",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No sale summary data.")

    with col_r:
        st.subheader("Rent — Avg Monthly Rent by Rooms")
        if not rent_sum.empty:
            fig = px.bar(
                rent_sum,
                x="rooms",
                y="avg_rent_price",
                labels={"rooms": "Rooms", "avg_rent_price": "Avg Rent (₪/mo)"},
                text="avg_rent_price",
                color_discrete_sequence=["#72B7B2"],
            )
            fig.update_traces(texttemplate="₪%{text:,.1f}", textposition="outside")
            fig.update_layout(showlegend=False, yaxis_tickformat=",.1f")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                rent_sum.rename(columns={
                    "rooms": "Rooms",
                    "avg_rent_price": "Avg (₪)",
                    "min_rent_price": "Min (₪)",
                    "max_rent_price": "Max (₪)",
                    "median_rent_price": "Median (₪)",
                    "count_rent": "Count",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No rent summary data.")

    # Price per sqm scatter
    st.subheader("Price per m² Distribution")
    scatter_col1, scatter_col2 = st.columns(2)

    with scatter_col1:
        if not sale_df.empty and "price_per_sqm" in sale_df.columns:
            valid = sale_df.dropna(subset=["price_per_sqm", "rooms"])
            if not valid.empty:
                fig = px.box(
                    valid,
                    x="rooms",
                    y="price_per_sqm",
                    labels={"rooms": "Rooms", "price_per_sqm": "₪/m²"},
                    title="Sale ₪/m² by Rooms",
                    color_discrete_sequence=["#4C78A8"],
                )
                st.plotly_chart(fig, use_container_width=True)

    with scatter_col2:
        if not rent_df.empty and "price_per_sqm" in rent_df.columns:
            valid = rent_df.dropna(subset=["price_per_sqm", "rooms"])
            if not valid.empty:
                fig = px.box(
                    valid,
                    x="rooms",
                    y="price_per_sqm",
                    labels={"rooms": "Rooms", "price_per_sqm": "₪/m²"},
                    title="Rent ₪/m² by Rooms",
                    color_discrete_sequence=["#72B7B2"],
                )
                st.plotly_chart(fig, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────────
# TAB 3 — BUY VS RENT
# ────────────────────────────────────────────────────────────────────────────────

with tab3:
    st.header("Buy vs Rent Comparison")

    if comp_df.empty:
        st.info("No comparison data. Both sale and rent data are needed.")
    else:
        # Summary table — rename first, then style
        display = comp_df.copy().rename(columns={
            "rooms": "Rooms",
            "avg_purchase_price": "Avg Buy Price",
            "avg_rent_price": "Avg Rent/mo",
            "avg_purchase_price_per_sqm": "Buy ₪/m²",
            "avg_rent_price_per_sqm": "Rent ₪/m²",
            "estimated_gross_yield": "Gross Yield",
            "sample_size_buy": "# Sale",
            "sample_size_rent": "# Rent",
        })
        fmt_map = {}
        if "Rooms" in display.columns:
            fmt_map["Rooms"] = fmt_rooms
        for col, fn in [("Avg Buy Price", fmt_price), ("Avg Rent/mo", fmt_price)]:
            if col in display.columns:
                fmt_map[col] = fn
        for col in ["Buy ₪/m²", "Rent ₪/m²"]:
            if col in display.columns:
                fmt_map[col] = fmt_ppsqm
        if "Gross Yield" in display.columns:
            fmt_map["Gross Yield"] = fmt_yield

        styled = display.style.format(fmt_map)
        if "Avg Rent/mo" in display.columns:
            styled = styled.applymap(flag_rent_price, subset=["Avg Rent/mo"])
        if "Rent ₪/m²" in display.columns:
            styled = styled.applymap(flag_rent_ppsqm, subset=["Rent ₪/m²"])
        if "Gross Yield" in display.columns:
            styled = styled.applymap(flag_yield, subset=["Gross Yield"])

        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Yield chart
        if "estimated_gross_yield" in comp_df.columns:
            valid_yield = comp_df.dropna(subset=["estimated_gross_yield"])
            # Filter out clearly bad data (yield > 20% is almost certainly a parse error)
            valid_yield = valid_yield[valid_yield["estimated_gross_yield"] < 0.20]
            if not valid_yield.empty:
                fig = px.bar(
                    valid_yield,
                    x="rooms",
                    y="estimated_gross_yield",
                    labels={"rooms": "Rooms", "estimated_gross_yield": "Gross Yield"},
                    text="estimated_gross_yield",
                    color_discrete_sequence=["#F58518"],
                    title="Estimated Gross Yield by Room Count",
                )
                fig.update_traces(
                    texttemplate="%{text:.2%}",
                    textposition="outside",
                )
                fig.update_layout(yaxis_tickformat=".1%")
                st.plotly_chart(fig, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────────
# TAB 4 — YIELD ESTIMATES
# ────────────────────────────────────────────────────────────────────────────────

with tab4:
    st.header("Per-Listing Yield Estimates")

    if yield_df.empty:
        st.info("No yield data.")
    else:
        # Filter out bad data
        valid = yield_df.copy()
        if "estimated_gross_yield" in valid.columns:
            valid = valid[
                valid["estimated_gross_yield"].isna() |
                (valid["estimated_gross_yield"] < 0.20)
            ]

        # Sort by yield descending
        if "estimated_gross_yield" in valid.columns:
            valid = valid.sort_values("estimated_gross_yield", ascending=False)

        # Room filter
        if "rooms" in valid.columns:
            rooms_opts = sorted(valid["rooms"].dropna().unique().tolist())
            sel = st.multiselect("Filter by rooms", rooms_opts, key="yield_rooms")
            if sel:
                valid = valid[valid["rooms"].isin(sel)]

        display = valid.copy().rename(columns={
            "address": "Address",
            "rooms": "Rooms",
            "size_sqm": "Size (m²)",
            "purchase_price": "Purchase Price",
            "avg_comparable_rent": "Est. Rent/mo",
            "comparable_rent_count": "# Comps",
            "estimated_gross_yield": "Gross Yield",
            "link": "Link",
        })
        fmt_map = {}
        if "Rooms" in display.columns:
            fmt_map["Rooms"] = fmt_rooms
        if "Purchase Price" in display.columns:
            fmt_map["Purchase Price"] = fmt_price
        if "Est. Rent/mo" in display.columns:
            fmt_map["Est. Rent/mo"] = fmt_price
        if "Gross Yield" in display.columns:
            fmt_map["Gross Yield"] = fmt_yield

        styled = display.style.format(fmt_map)
        if "Est. Rent/mo" in display.columns:
            styled = styled.applymap(flag_rent_price, subset=["Est. Rent/mo"])
        if "Gross Yield" in display.columns:
            styled = styled.applymap(flag_yield, subset=["Gross Yield"])

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open ↗")},
        )

        # Scatter: price vs yield
        valid2 = yield_df.dropna(subset=["purchase_price", "estimated_gross_yield"])
        valid2 = valid2[valid2["estimated_gross_yield"] < 0.20]
        if not valid2.empty:
            valid2["address_clean"] = valid2["address"].apply(clean_address)
            fig = px.scatter(
                valid2,
                x="purchase_price",
                y="estimated_gross_yield",
                size="size_sqm",
                color="rooms",
                hover_name="address_clean",
                hover_data={"purchase_price": ":,.0f", "estimated_gross_yield": ":.2%"},
                labels={
                    "purchase_price": "Purchase Price (₪)",
                    "estimated_gross_yield": "Gross Yield",
                    "rooms": "Rooms",
                },
                title="Purchase Price vs Gross Yield",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(yaxis_tickformat=".1%", xaxis_tickformat=",.1f")
            st.plotly_chart(fig, use_container_width=True)


# ────────────────────────────────────────────────────────────────────────────────
# TAB 5 — MORTGAGE CALCULATOR
# ────────────────────────────────────────────────────────────────────────────────

with tab5:
    st.header("Mortgage Calculator")

    # ── Inputs ───────────────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        # Pre-fill with average sale price from loaded data if available
        default_price = 0
        if not sale_df.empty and "price" in sale_df.columns:
            avg = sale_df["price"].dropna()
            default_price = int(avg.mean()) if not avg.empty else 0
        price = st.number_input(
            "Purchase Price (₪)",
            min_value=0,
            value=default_price,
            step=50_000,
            format="%d",
        )

    with col_b:
        ltv = st.slider("Loan to Value — LTV (%)", min_value=10, max_value=90, value=75, step=5)
        down = price * (1 - ltv / 100)
        st.caption(f"Down payment: ₪{down:,.0f}  |  Loan: ₪{price - down:,.0f}")

    with col_c:
        interest = st.number_input("Annual Interest Rate (%)", min_value=0.1, max_value=20.0, value=4.5, step=0.1)

    years_options = [10, 15, 20, 25, 30]
    selected_years = st.multiselect(
        "Loan durations to compare (years)",
        options=years_options,
        default=[15, 20, 25, 30],
    )

    # Monthly rent input — pre-fill from rent data if available
    default_rent = 0
    if not rent_df.empty and "price" in rent_df.columns:
        avg_rent = rent_df["price"].dropna()
        avg_rent = avg_rent[avg_rent < 30_000]   # exclude obvious bad data
        default_rent = int(avg_rent.mean()) if not avg_rent.empty else 0
    monthly_rent = st.number_input(
        "Expected Monthly Rent (₪)  — for cash flow calculation",
        min_value=0,
        value=default_rent,
        step=500,
        format="%d",
    )

    st.markdown("---")

    # ── Run simulation ────────────────────────────────────────────────────────────
    if price > 0 and selected_years:
        scenarios = simulate_mortgage_scenarios(
            price=float(price),
            ltv_percent=float(ltv),
            annual_interest=float(interest),
            years_list=selected_years,
        )

        if scenarios:
            df_scen = pd.DataFrame(scenarios)

            # Add cash flow column
            df_scen["monthly_cash_flow"] = df_scen["monthly_payment"].apply(
                lambda mp: calculate_cash_flow(float(monthly_rent), mp) if monthly_rent > 0 else None
            )

            # ── Summary cards ─────────────────────────────────────────────────────
            st.subheader("Scenario Comparison")
            metric_cols = st.columns(len(scenarios))
            for col, s in zip(metric_cols, scenarios):
                cf = calculate_cash_flow(float(monthly_rent), s["monthly_payment"]) if monthly_rent > 0 else None
                cf_str = f"{cf:+,.0f} ₪/mo" if cf is not None else "—"
                col.metric(
                    label=f"{s['years']} years",
                    value=f"₪{s['monthly_payment']:,.0f}/mo",
                    delta=cf_str,
                    delta_color="normal",
                )

            # ── Table ─────────────────────────────────────────────────────────────
            display = df_scen.copy().rename(columns={
                "years":                  "Years",
                "down_payment":           "Down Payment",
                "loan_amount":            "Loan",
                "monthly_payment":        "Monthly Payment",
                "total_payment":          "Total Payment",
                "total_interest":         "Total Interest",
                "interest_to_loan_ratio": "Interest / Loan",
                "monthly_cash_flow":      "Cash Flow / mo",
            })

            fmt = {
                "Down Payment":    fmt_price,
                "Loan":            fmt_price,
                "Monthly Payment": fmt_price,
                "Total Payment":   fmt_price,
                "Total Interest":  fmt_price,
                "Interest / Loan": lambda x: f"{x:.1%}" if pd.notna(x) else "—",
                "Cash Flow / mo":  lambda x: f"₪{x:+,.0f}" if pd.notna(x) else "—",
            }

            def color_cashflow(val):
                try:
                    n = float(str(val).replace("₪", "").replace(",", "").replace("+", ""))
                    if n >= 0:
                        return "background-color: #21c354; color: white;"
                    return RED_BG
                except (ValueError, TypeError):
                    return CLEAR_BG

            styled = display.style.format(fmt)
            if "Cash Flow / mo" in display.columns:
                styled = styled.applymap(color_cashflow, subset=["Cash Flow / mo"])

            st.dataframe(styled, use_container_width=True, hide_index=True)

            # ── Charts ────────────────────────────────────────────────────────────
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                fig = px.bar(
                    df_scen,
                    x="years",
                    y="monthly_payment",
                    text="monthly_payment",
                    labels={"years": "Loan Duration (years)", "monthly_payment": "Monthly Payment (₪)"},
                    title="Monthly Payment by Duration",
                    color_discrete_sequence=["#4C78A8"],
                )
                fig.update_traces(texttemplate="₪%{text:,.0f}", textposition="outside")
                fig.update_layout(yaxis_tickformat=",.0f")
                st.plotly_chart(fig, use_container_width=True)

            with chart_col2:
                fig = px.bar(
                    df_scen,
                    x="years",
                    y=["loan_amount", "total_interest"],
                    labels={
                        "years": "Loan Duration (years)",
                        "value": "Amount (₪)",
                        "variable": "",
                    },
                    title="Principal vs Total Interest Paid",
                    barmode="stack",
                    color_discrete_map={
                        "loan_amount":    "#4C78A8",
                        "total_interest": "#F58518",
                    },
                )
                fig.update_layout(yaxis_tickformat=",.0f")
                st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Enter a purchase price and select at least one loan duration to see results.")
