#!/usr/bin/env python3

import sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from playwright.sync_api import sync_playwright, Page

OUT_DIR = Path("./yad2_output")
OUT_DIR.mkdir(exist_ok=True)

SALE_URL = "https://www.yad2.co.il/realestate/forsale?property=1&propertyGroup=apartments"
RENT_URL = "https://www.yad2.co.il/realestate/rent?property=1&propertyGroup=apartments"


@dataclass
class Listing:
    price: Optional[float]
    rooms: Optional[float]
    size_sqm: Optional[float]
    floor: str
    address: str
    link: str
    source: str


def parse_number(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace(",", "")
    match = re.search(r"\d{3,9}", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def parse_price_from_card_text(text: str) -> Optional[float]:
    """Extract price from raw card text. Prefers ₪ sign; falls back to largest plausible number."""
    if not text:
        return None
    # Prefer number following ₪ sign
    m = re.search(r'[₪]\s*([\d,]+)', text)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    # Fallback: find all numbers and pick the first one >= 1000 (prices are never < 1000)
    for match in re.finditer(r'[\d,]+', text):
        raw = match.group().replace(',', '')
        try:
            val = float(raw)
            if val >= 1000:
                return val
        except ValueError:
            pass
    return None


def parse_rooms_from_card_text(text: str) -> Optional[float]:
    """Extract room count from Hebrew card text (e.g. '4 חדרים', '3.5 חדרים')."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*חדרים', text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def parse_size_from_card_text(text: str) -> Optional[float]:
    """Extract size in sqm from Hebrew card text (e.g. '88 מ״ר', '88 מ"ר')."""
    m = re.search(r'(\d+)\s*מ[״"\'׳]', text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def parse_floor_from_card_text(text: str) -> str:
    """Extract floor from Hebrew card text (e.g. 'קומה 3', 'קומה קרקע')."""
    m = re.search(r'קומה\s*\u200e?(\S+)', text)
    if m:
        return m.group(1).strip('\u200f')
    return ""


def parse_address_from_card_text(text: str) -> str:
    """
    Yad2 feedItem text has a consistent structure:
      Line 0: street name  (e.g. 'צפת 3')
      Line 1: type + area  (e.g. 'דירה, קרית שרת מערב, חולון')
      Line 2: rooms/floor/size details
    Returns 'street | area' from the first two non-empty lines.
    """
    # Strip helper tokens Yad2 injects (e.g. 'בלעדי', 'עולם הנדל"ן')
    noise = {'בלעדי', 'עולם הנדל"ן', 'מומלץ', 'חדש', 'NEW', 'EXCLUSIVE'}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    clean = [l for l in lines if l not in noise and not l.startswith('₪')]
    if len(clean) >= 2:
        return f"{clean[0]} | {clean[1]}"
    elif clean:
        return clean[0]
    return "Not specified"


def safe_text(text: Optional[str]) -> str:
    if isinstance(text, str) and text.strip():
        return text.strip()
    return "Not specified"


def calc_price_per_sqm(price: Optional[float], sqm: Optional[float]) -> Optional[float]:
    if price is None or sqm is None or sqm <= 0:
        return None
    return round(price / sqm, 2)


def estimate_yield(price: Optional[float], avg_rent: Optional[float]) -> Optional[float]:
    if price is None or avg_rent is None or price <= 0:
        return None
    return round((avg_rent * 12.0) / price, 4)


def first_text(card, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            loc = card.locator(selector).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=1000).strip()
                if txt:
                    return txt
        except Exception:
            pass
    return ""


def first_attr(card, selectors: List[str], attr: str) -> str:
    for selector in selectors:
        try:
            loc = card.locator(selector).first
            if loc.count() > 0:
                val = loc.get_attribute(attr, timeout=1000)
                if val:
                    return val.strip()
        except Exception:
            pass
    return ""


def scroll_and_load(page: Page, cycles: int = 10) -> None:
    previous_height = 0
    stable_count = 0
    for i in range(cycles):
        try:
            page.mouse.wheel(0, 5000)
        except Exception:
            pass
        # Wait for network to settle after each scroll
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            time.sleep(1.5)

        for selector in [
            'button:has-text("טען עוד")',
            'button:has-text("עוד")',
            'button:has-text("Load more")',
            '[data-testid="load-more"]',
            '[data-testid="pagination-next"]',
        ]:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=1500)
                    try:
                        page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:
                        time.sleep(1.5)
                    break
            except Exception:
                pass

        try:
            height = page.evaluate("document.body.scrollHeight")
            if height == previous_height:
                stable_count += 1
                if stable_count >= 3:
                    print(f"  Page height stable after {i+1} scroll cycles — stopping early.")
                    break
            else:
                stable_count = 0
                previous_height = height
        except Exception:
            pass


def _dump_debug_files(page: Page, source: str, out_dir: Path = OUT_DIR) -> None:
    """Dump HTML and screenshot for DOM inspection when selectors fail."""
    debug_html_path = out_dir / f"debug_{source}_page.html"
    debug_png_path = out_dir / f"debug_{source}_page.png"
    try:
        html = page.content()
        debug_html_path.write_text(html, encoding="utf-8")
        print(f"  [DEBUG] Page HTML saved → {debug_html_path.resolve()}")
    except Exception as e:
        print(f"  [DEBUG] Could not save HTML: {e}")
    try:
        page.screenshot(path=str(debug_png_path), full_page=True)
        print(f"  [DEBUG] Screenshot saved → {debug_png_path.resolve()}")
    except Exception as e:
        print(f"  [DEBUG] Could not save screenshot: {e}")


def extract_listings(page: Page, source: str) -> List[Listing]:
    # ── Selector priority list ──────────────────────────────────────────────
    # Add more candidates here if Yad2 changes its DOM.
    card_selectors = [
        # testid-based (most reliable if present)
        '[data-testid="item-card"]',
        '[data-testid="feed-item"]',
        '[data-testid="feeditem"]',
        # Yad2 React class patterns (obfuscated but stable prefixes)
        'div[class*="feedItem"]',
        'div[class*="feed-item"]',
        'div[class*="feeditem"]',
        'div[class*="item-card"]',
        'div[class*="ItemCard"]',
        'div[class*="listingCard"]',
        'div[class*="listing-card"]',
        # li-based feed lists
        'li[class*="feed"]',
        'li[class*="item"]',
        # generic fallback — last resort, may over-match
        'article',
    ]

    # ── Probe every selector and log counts ─────────────────────────────────
    print(f"\n[{source}] Probing selectors:")
    cards = None
    for selector in card_selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()
        except Exception as exc:
            print(f"  {selector!r:50s} → ERROR: {exc}")
            count = 0
        print(f"  {selector!r:50s} → {count} elements")
        if count > 0 and cards is None:
            cards = loc
            winning_selector = selector

    if cards is None:
        print(f"\n[{source}] ERROR: No listing cards found with any known selector.")
        print(f"[{source}] Dumping debug files so you can inspect the real DOM...")
        _dump_debug_files(page, source)
        return []

    total = cards.count()
    print(f"\n[{source}] Using selector: {winning_selector!r} → {total} cards")

    # ── Log first card's raw text as a sanity check ─────────────────────────
    try:
        first_card_text = cards.nth(0).inner_text(timeout=2000).replace("\n", " | ")[:200]
        print(f"[{source}] First card text sample: {first_card_text!r}")
    except Exception:
        pass

    # ── Extract data from each card ──────────────────────────────────────────
    results: List[Listing] = []
    skipped = 0

    for i in range(total):
        card = cards.nth(i)

        # Get the full raw text of the card — this is our primary data source.
        # Yad2's feedItem cards embed all data as text; sub-selectors for individual
        # fields are unreliable due to obfuscated React class names.
        card_text = ""
        try:
            card_text = card.inner_text(timeout=1500)
        except Exception:
            pass

        # Try sub-selectors for price first (most likely to have a dedicated element).
        # Fall back to text-based parsing which handles all known Yad2 card formats.
        price_text = first_text(card, [
            '[data-testid="item-price"]',
            '[data-testid="price"]',
            '[class*="price"]',
            '[class*="Price"]',
        ])
        price = parse_price(price_text) or parse_price_from_card_text(card_text)

        # Rooms, size, floor, address: always parse from card text — more reliable
        # than sub-selectors which vary across card types (organic, sponsored, etc.).
        rooms = parse_rooms_from_card_text(card_text)
        size_sqm = parse_size_from_card_text(card_text)
        floor = parse_floor_from_card_text(card_text)
        address = parse_address_from_card_text(card_text)

        link = first_attr(card, ['a[href*="/realestate/"]', 'a[href*="/item/"]', 'a'], 'href')
        if link and link.startswith('/'):
            link = 'https://www.yad2.co.il' + link

        # Skip cards with zero useful data (ads, banners, empty slots)
        has_data = any([
            price is not None,
            rooms is not None,
            size_sqm is not None,
            address != "Not specified",
            bool(link),
        ])
        if not has_data:
            skipped += 1
            continue

        results.append(Listing(
            price=price,
            rooms=rooms,
            size_sqm=size_sqm,
            floor=floor,
            address=address,
            link=safe_text(link),
            source=source,
        ))

    print(f"[{source}] Extracted {len(results)} listings ({skipped} cards skipped as empty/ads).")

    if len(results) == 0:
        print(f"[{source}] WARNING: Selector matched {total} cards but all parsed empty.")
        print(f"[{source}] This usually means sub-selectors are wrong. Dumping debug files...")
        _dump_debug_files(page, source)

    return results


def open_and_collect(
    page: Page, url: str, source: str, load_cycles: int = 10
) -> Tuple[List[Listing], str]:
    """
    Open a Yad2 page, let the user set filters, then scrape.
    Returns (listings, location_slug) where location_slug is parsed from the
    page URL after the user has applied their filters.
    """
    print(f"\nOpening {source} page...")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        time.sleep(4)

    print(f"\n{'='*60}")
    print(f"  [{source.upper()}] Set your filters in the browser tab now.")
    print(f"  When results are fully visible, come back here and press Enter.")
    print(f"{'='*60}")
    input("  Press Enter when ready → ")

    # Wait for page to settle after filter changes
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        time.sleep(2)

    # Capture location from URL now — after filters are applied
    location = extract_location_from_page(page)
    print(f"[{source}] Detected location: {location!r}")

    print(f"[{source}] Starting scroll & load ({load_cycles} cycles)...")
    scroll_and_load(page, cycles=load_cycles)
    return extract_listings(page, source), location


def add_price_per_sqm(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["price_per_sqm"] = df.apply(lambda row: calc_price_per_sqm(row.get("price"), row.get("size_sqm")), axis=1)
    return df


def summarize_by_rooms(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "rooms", f"avg_{prefix}_price", f"min_{prefix}_price", f"max_{prefix}_price",
            f"median_{prefix}_price", f"count_{prefix}"
        ])

    valid = df.dropna(subset=["rooms", "price"])
    if valid.empty:
        return pd.DataFrame(columns=[
            "rooms", f"avg_{prefix}_price", f"min_{prefix}_price", f"max_{prefix}_price",
            f"median_{prefix}_price", f"count_{prefix}"
        ])

    out = valid.groupby("rooms", as_index=False).agg(
        **{
            f"avg_{prefix}_price": ("price", "mean"),
            f"min_{prefix}_price": ("price", "min"),
            f"max_{prefix}_price": ("price", "max"),
            f"median_{prefix}_price": ("price", "median"),
            f"count_{prefix}": ("price", "count"),
        }
    ).sort_values("rooms")

    for col in out.columns:
        if col != "rooms":
            out[col] = out[col].map(lambda x: round(x, 2) if pd.notna(x) else x)
    return out


def build_sale_yield_table(sale_df: pd.DataFrame, rent_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "purchase_price", "rooms", "size_sqm", "address", "avg_comparable_rent",
        "comparable_rent_count", "estimated_gross_yield", "link"
    ]
    if sale_df.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for _, sale_row in sale_df.iterrows():
        comps = rent_df.copy()

        if pd.notna(sale_row.get("rooms")):
            comps = comps[comps["rooms"] == sale_row["rooms"]]

        if pd.notna(sale_row.get("size_sqm")):
            s = float(sale_row["size_sqm"])
            comps = comps[
                comps["size_sqm"].isna() |
                ((comps["size_sqm"] >= s * 0.8) & (comps["size_sqm"] <= s * 1.2))
            ]

        comps = comps.dropna(subset=["price"])
        avg_rent = comps["price"].mean() if not comps.empty else None
        rent_count = int(len(comps))
        gross_yield = estimate_yield(sale_row.get("price"), avg_rent)

        rows.append({
            "purchase_price": sale_row.get("price"),
            "rooms": sale_row.get("rooms"),
            "size_sqm": sale_row.get("size_sqm"),
            "address": sale_row.get("address"),
            "avg_comparable_rent": round(avg_rent, 2) if avg_rent is not None and not pd.isna(avg_rent) else None,
            "comparable_rent_count": rent_count,
            "estimated_gross_yield": gross_yield,
            "link": sale_row.get("link"),
        })

    return pd.DataFrame(rows, columns=columns)


def build_buy_rent_comparison(sale_df: pd.DataFrame, rent_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "rooms", "avg_purchase_price", "avg_rent_price",
        "avg_purchase_price_per_sqm", "avg_rent_price_per_sqm",
        "estimated_gross_yield", "sample_size_buy", "sample_size_rent"
    ]

    if sale_df.empty or rent_df.empty:
        return pd.DataFrame(columns=columns)

    sale_valid = sale_df.dropna(subset=["rooms", "price"])
    rent_valid = rent_df.dropna(subset=["rooms", "price"])
    if sale_valid.empty or rent_valid.empty:
        return pd.DataFrame(columns=columns)

    sale_group = sale_valid.groupby("rooms", as_index=False).agg(
        avg_purchase_price=("price", "mean"),
        avg_purchase_price_per_sqm=("price_per_sqm", "mean"),
        sample_size_buy=("price", "count"),
    )
    rent_group = rent_valid.groupby("rooms", as_index=False).agg(
        avg_rent_price=("price", "mean"),
        avg_rent_price_per_sqm=("price_per_sqm", "mean"),
        sample_size_rent=("price", "count"),
    )

    merged = sale_group.merge(rent_group, on="rooms", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=columns)

    merged["estimated_gross_yield"] = merged.apply(
        lambda row: estimate_yield(row.get("avg_purchase_price"), row.get("avg_rent_price")), axis=1
    )

    for col in merged.columns:
        if col != "rooms":
            merged[col] = merged[col].map(lambda x: round(x, 4) if pd.notna(x) and isinstance(x, (int, float, np.floating)) else x)

    return merged[columns].sort_values("rooms")


def extract_location_from_page(page: Page) -> str:
    """
    Parse the Yad2 URL after the user sets filters to extract a location slug.

    Yad2 updates the URL path to include the area when a neighborhood is selected:
      /realestate/forsale/flats-old-north-north-in-tel-aviv-yafo?city=5000&...
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    Returns a cleaned string like 'old_north_north_in_tel_aviv_yafo'.
    Falls back to 'unknown_area' if the URL can't be parsed.
    """
    try:
        path = urlparse(page.url).path          # /realestate/rent/<slug>
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3:
            slug = parts[2]
            # Strip Yad2 property-type prefixes that precede the location
            for prefix in (
                "flats-", "apartments-", "penthouse-", "rooms-",
                "cottage-", "garden-apartment-", "warehouses-",
            ):
                if slug.startswith(prefix):
                    slug = slug[len(prefix):]
                    break
            return slug.replace("-", "_")
        return parts[-1].replace("-", "_") if parts else "unknown_area"
    except Exception:
        return "unknown_area"


def make_output_dir(slug: str) -> Path:
    clean = re.sub(r"[^\w\u0590-\u05ff]+", "_", slug).strip("_") or "unknown_area"
    out = OUT_DIR / clean
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_outputs(out_dir: Path, sale_df: pd.DataFrame, rent_df: pd.DataFrame, sale_summary: pd.DataFrame, rent_summary: pd.DataFrame, comparison_df: pd.DataFrame, yield_df: pd.DataFrame) -> None:
    sale_df.to_csv(out_dir / "sale_raw_listings.csv", index=False, encoding="utf-8-sig")
    rent_df.to_csv(out_dir / "rent_raw_listings.csv", index=False, encoding="utf-8-sig")
    sale_summary.to_csv(out_dir / "sale_summary_by_rooms.csv", index=False, encoding="utf-8-sig")
    rent_summary.to_csv(out_dir / "rent_summary_by_rooms.csv", index=False, encoding="utf-8-sig")
    comparison_df.to_csv(out_dir / "buy_rent_comparison.csv", index=False, encoding="utf-8-sig")
    yield_df.to_csv(out_dir / "sale_listing_yield_estimates.csv", index=False, encoding="utf-8-sig")


def print_preview(title: str, df: pd.DataFrame, max_rows: int = 10) -> None:
    print(f"\n{title}")
    if df.empty:
        print("No data")
        return
    print(df.head(max_rows).to_string(index=False))


def main() -> None:
    print("Yad2 Buy vs Rent Analyzer")
    print("The script will open sale and rent pages. Set filters manually in the browser, then press Enter in the terminal.")
    print("The output folder name will be detected automatically from the page URL.\n")

    load_cycles_raw = input("How many load/scroll cycles to try? [default 10]: ").strip()
    load_cycles = int(load_cycles_raw) if load_cycles_raw.isdigit() else 10

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        sale_page = browser.new_page()
        rent_page = browser.new_page()

        sale_df = pd.DataFrame()
        rent_df = pd.DataFrame()

        sale_rows, sale_location = open_and_collect(sale_page, SALE_URL, "sale", load_cycles=load_cycles)
        rent_rows, _             = open_and_collect(rent_page, RENT_URL, "rent", load_cycles=load_cycles)

        browser.close()

    # Use location from sale page URL; fall back to rent if sale was generic
    location = sale_location if sale_location != "unknown_area" else "unknown_area"
    out_dir = make_output_dir(location)
    print(f"\nOutput folder: {out_dir.resolve()}")

    if sale_rows:
        sale_df = pd.DataFrame([asdict(x) for x in sale_rows])
        if not sale_df.empty and "link" in sale_df.columns:
            sale_df = sale_df.drop_duplicates(subset=["link"], keep="first")
        sale_df = add_price_per_sqm(sale_df)
    else:
        print("No sale rows were extracted.")
        sale_df = pd.DataFrame(columns=["price", "rooms", "size_sqm", "floor", "address", "link", "source", "price_per_sqm"])

    if rent_rows:
        rent_df = pd.DataFrame([asdict(x) for x in rent_rows])
        if not rent_df.empty and "link" in rent_df.columns:
            rent_df = rent_df.drop_duplicates(subset=["link"], keep="first")
        rent_df = add_price_per_sqm(rent_df)
    else:
        print("No rent rows were extracted.")
        rent_df = pd.DataFrame(columns=["price", "rooms", "size_sqm", "floor", "address", "link", "source", "price_per_sqm"])

    sale_summary = summarize_by_rooms(sale_df, "sale")
    rent_summary = summarize_by_rooms(rent_df, "rent")
    comparison_df = build_buy_rent_comparison(sale_df, rent_df)
    yield_df = build_sale_yield_table(sale_df, rent_df)

    print_preview("Sale preview", sale_df)
    print_preview("Rent preview", rent_df)
    print_preview("Buy vs Rent comparison", comparison_df)
    print_preview("Per-sale yield estimates", yield_df)

    save_outputs(out_dir, sale_df, rent_df, sale_summary, rent_summary, comparison_df, yield_df)

    print("\nSaved files:")
    for fname in [
        "sale_raw_listings.csv",
        "rent_raw_listings.csv",
        "sale_summary_by_rooms.csv",
        "rent_summary_by_rooms.csv",
        "buy_rent_comparison.csv",
        "sale_listing_yield_estimates.csv",
    ]:
        print(f"  {(out_dir / fname).resolve()}")
    print("\nDone.")


if __name__ == "__main__":
    main()
