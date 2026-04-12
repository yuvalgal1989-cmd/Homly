# Yad2 Buy vs Rent Analyzer

A local Python tool that scrapes **apartments for sale** and **apartments for rent** from [Yad2](https://www.yad2.co.il), then analyzes them to estimate **market rent**, **potential gross yield**, and **mortgage costs** for each property.

---

## How It Works

1. Opens two browser tabs (Playwright) — one for sale, one for rent
2. You manually apply filters in the browser (city, neighborhood, rooms, etc.)
3. You press Enter in the terminal
4. The script scrolls the page to load all listings, then scrapes them
5. Data is parsed, analyzed, and saved as CSV files
6. Open the Streamlit dashboard to explore results visually

The browser stays visible throughout — filters are never automated.

---

## What Gets Extracted

For each listing:

| Field | Description |
|---|---|
| `price` | Asking price (sale) or monthly rent |
| `rooms` | Number of rooms |
| `size_sqm` | Size in square meters |
| `floor` | Floor number |
| `address` | Street and neighborhood |
| `link` | Direct URL to the listing |
| `price_per_sqm` | Calculated: price ÷ size |

---

## Output Files

All files are saved to `./yad2_output/{city}_{neighborhood}/` — a separate folder per search:

| File | Contents |
|---|---|
| `sale_raw_listings.csv` | All scraped sale listings with derived fields |
| `rent_raw_listings.csv` | All scraped rent listings with derived fields |
| `sale_summary_by_rooms.csv` | Avg / min / max / median price grouped by room count (sale) |
| `rent_summary_by_rooms.csv` | Avg / min / max / median price grouped by room count (rent) |
| `buy_rent_comparison.csv` | Side-by-side buy vs rent stats per room count |
| `sale_listing_yield_estimates.csv` | Estimated gross yield for each sale listing |

---

## Yield Estimation

For each sale listing, the tool finds comparable rent listings (same room count, ±20% size) and calculates:

```
Gross Yield = (Average Comparable Rent × 12) / Purchase Price
```

---

## Mortgage Calculator

A standalone module (`mortgage.py`) with no external dependencies:

| Function | Description |
|---|---|
| `calculate_down_payment(price, ltv_percent)` | Down payment based on LTV |
| `calculate_loan_amount(price, down_payment)` | Principal = price − down payment |
| `calculate_monthly_payment(loan, interest, years)` | Standard annuity formula |
| `calculate_total_payment(monthly, years)` | Total paid over loan term |
| `calculate_total_interest(total, loan)` | Total interest = total − principal |
| `calculate_cash_flow(monthly_rent, monthly_payment)` | Net monthly cash flow |
| `simulate_mortgage_scenarios(price, ltv, interest, years_list)` | Compare multiple durations |

```python
from mortgage import simulate_mortgage_scenarios
scenarios = simulate_mortgage_scenarios(
    price=2_500_000, ltv_percent=75, annual_interest=4.5, years_list=[15, 20, 25, 30]
)
```

---

## Streamlit Dashboard

An interactive dashboard (`dashboard.py`) with 5 tabs:

| Tab | Contents |
|---|---|
| 📋 Listings | Sale and rent tables, filterable by rooms, clickable links |
| 📊 Market Stats | Avg price and ₪/m² charts by room count |
| ⚖️ Buy vs Rent | Side-by-side comparison table and gross yield bar chart |
| 💰 Yield Estimates | Per-listing yield table + price vs yield scatter plot |
| 🏦 Mortgage Calculator | Scenario comparison, cash flow, payment and interest charts |

Suspicious values (rent > ₪30k, yield > 15%, ₪/m² > ₪500) are highlighted in red automatically.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

pip install playwright pandas numpy streamlit plotly
playwright install chromium
```

---

## Usage

### Run the scraper

```bash
python yad2_rental_analyzer.py
```

1. Enter the **city** and **neighborhood** — this becomes the output folder name
2. Enter the number of scroll cycles (default: 10)
3. The browser opens the **sale** page — apply your filters, then press Enter
4. The browser opens the **rent** page — apply your filters, then press Enter
5. Results are saved to `yad2_output/{city}_{neighborhood}/`

### Launch the dashboard

```bash
streamlit run dashboard.py
```

---

## Debugging

If scraping returns empty results, the script automatically saves:

- `yad2_output/.../debug_sale_page.html` — full DOM at time of extraction
- `yad2_output/.../debug_sale_page.png` — screenshot at time of extraction
- Same for rent

The terminal also prints a selector probe table showing match counts per selector and a sample of the first card's raw text.

---

## Known Limitations

- Yad2 requires a non-blocked browser session — if the page loads empty, try opening it in a regular browser first
- Sponsored listings and banners are filtered out during parsing
- Gross yield is an estimate — it does not account for taxes, maintenance, vacancy, or financing costs
- Mortgage calculations assume a fixed interest rate for the full term
