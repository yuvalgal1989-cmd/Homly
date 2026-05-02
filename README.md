# Homly — Real Estate Analyzer

A tool that scrapes apartments for sale and for rent from [Yad2](https://www.yad2.co.il), then analyzes them — market rent, gross yield, and mortgage costs per listing.

---

## Two Ways to Use It

### On Your Mac (scraping + viewing)

This is where the actual scraping happens. You always need your Mac for this.

```bash
python homly.py
```

1. A browser opens — apply your filters (city, neighborhood, rooms, etc.)
2. Press Enter in the terminal
3. The script scrolls and scrapes the page
4. Results are saved to `yad2_output/{area}/`

Then launch the dashboard locally:

```bash
streamlit run dashboard.py
```

After scraping, push the results so you can see them from the web too:

```bash
./push_data.sh
```

---

### From the Web (viewing only)

Once deployed to Streamlit Cloud, you can open the dashboard from any device — phone, work computer, anywhere.

The web app is **read-only**. You can browse all your scraped data, filter listings, run mortgage scenarios, and check yields — but you cannot start a new scrape from there.

To add new data: scrape on your Mac, then run `./push_data.sh`. The web dashboard updates within ~30 seconds.

---

## Setup (first time)

```bash
python -m venv .venv
source .venv/bin/activate

pip install playwright pandas numpy streamlit plotly
playwright install chromium
```

---

## Deploy to the Web (one time)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Set: repo = `yuvalgal1989-cmd/Homly`, branch = `main`, file = `dashboard.py`
4. Click **Deploy**

You'll get a public URL you can open from anywhere.

---

## Output Files

Saved to `yad2_output/{area}/` after each scrape:

| File | Contents |
|---|---|
| `sale_raw_listings.csv` | All sale listings |
| `rent_raw_listings.csv` | All rent listings |
| `sale_summary_by_rooms.csv` | Avg / min / max / median by room count (sale) |
| `rent_summary_by_rooms.csv` | Avg / min / max / median by room count (rent) |
| `buy_rent_comparison.csv` | Side-by-side buy vs rent stats |
| `sale_listing_yield_estimates.csv` | Estimated gross yield per listing |

---

## Dashboard Tabs

| Tab | What it shows |
|---|---|
| Listings | Sale and rent tables, filterable by rooms, clickable links |
| Market Stats | Avg price and ₪/m² charts by room count |
| Buy vs Rent | Comparison table and gross yield chart |
| Yield Estimates | Per-listing yield table + price vs yield scatter |
| Mortgage Calculator | Scenario comparison, cash flow, payment charts |

Suspicious values (rent > ₪30k, yield > 15%) are highlighted in red.

---

## Yield Estimation

For each sale listing, finds comparable rent listings (same room count, ±20% size):

```
Gross Yield = (Average Comparable Rent × 12) / Purchase Price
```

---

## Mortgage Calculator

Standalone module (`mortgage.py`), no external dependencies:

```python
from mortgage import simulate_mortgage_scenarios
scenarios = simulate_mortgage_scenarios(
    price=2_500_000, ltv_percent=75, annual_interest=4.5, years_list=[15, 20, 25, 30]
)
```

---

## Known Limitations

- Yad2 requires a real browser session — if the page loads empty, open it in a regular browser first
- Gross yield is an estimate — does not account for taxes, maintenance, or vacancy
- Mortgage calculations assume a fixed interest rate for the full term
