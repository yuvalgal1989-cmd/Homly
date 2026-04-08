# Yad2 Buy vs Rent Analyzer

A local Python tool that scrapes **apartments for sale** and **apartments for rent** from [Yad2](https://www.yad2.co.il), then compares them to estimate **market rent** and **potential gross yield** for each sale listing.

---

## How It Works

1. Opens two browser tabs (Playwright) — one for sale, one for rent
2. You manually apply filters in the browser (city, neighborhood, rooms, etc.)
3. You press Enter in the terminal
4. The script scrolls the page to load all listings, then scrapes them
5. Data is parsed, analyzed, and saved as CSV files

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

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

pip install playwright pandas numpy
playwright install chromium
```

---

## Usage

```bash
python yad2_rental_analyzer.py
```

1. Enter the **city** and **neighborhood** — this becomes the output folder name
2. Enter the number of scroll cycles (default: 10)
3. The browser opens the **sale** page — apply your filters, then press Enter
4. The browser opens the **rent** page — apply your filters, then press Enter
5. Results are saved to `yad2_output/{city}_{neighborhood}/`

---

## Debugging

If selectors fail or data looks wrong, the script automatically saves:

- `yad2_output/debug_sale_page.html` — full DOM of the sale page
- `yad2_output/debug_sale_page.png` — screenshot at time of extraction
- `yad2_output/debug_rent_page.html` / `.png` — same for rent

The terminal also prints a selector probe table showing how many elements each selector matched, and a sample of the first card's raw text.

---

## Known Limitations

- Yad2 requires a logged-in or non-blocked session — if the page loads empty, try opening it manually in a regular browser first
- Sponsored listings and banners are filtered out during parsing
- Gross yield is an estimate only — it does not account for taxes, maintenance, vacancy, or financing
