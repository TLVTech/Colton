# scrapers/run_scraper.py
import os
from fydafreightlinerV2 import (
    get_target_listings,
    get_vehicle_page_html,
    extract_vehicle_info,
    make_extracted_info_compliant,
    writeToCSV,
    write_failed_url
)

def main():

    dealer_url = "https://www.fydafreightliner.com/commercial-trucks-vans-for-sale-ky-oh-pa--xNewInventory#"

    print("▶️  Fetching listing URLs…")
    all_urls, all_texts = get_target_listings(dealer_url)
    print(f"→ Found {len(all_urls)} total listings.")

    if not all_urls:
        print("⚠️ No listings found. Exiting.")
        return

    # Create an output folder one level up from scrapers/:
    output_csv = os.path.join(os.path.dirname(__file__), "..", "output", "vehicles.csv")
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    for idx, url in enumerate(all_urls, start=1):
        print(f"\n---- Scraping detail page {idx}/{len(all_urls)}: {url} ----")
        raw_text = get_vehicle_page_html(url)
        if not raw_text:
            print(f"❌ No text for {url}; skipping.")
            write_failed_url(url)
            continue

        parsed = extract_vehicle_info(raw_text)
        if parsed is None:
            print(f"❌ GPT parse failed for {url}; skipping.")
            write_failed_url(url)
            continue

        normalized = make_extracted_info_compliant(parsed)
        writeToCSV(normalized, attributes=None, filename=output_csv)
        print(f"✅ Saved data for {url} to {output_csv}")

    print("\n🎉  Scrape complete. Check the CSV at:", output_csv)

if __name__ == "__main__":
    main()
