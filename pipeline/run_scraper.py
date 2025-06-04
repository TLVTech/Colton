# Colton/pipeline/run_scraper.py
import os
from scrapers.jasper_trucks import get_target_listings, run

if __name__ == "__main__":
    listings = get_target_listings()
    print(f"Total listings found: {len(listings)}")

    # Create results folders
    os.makedirs("results", exist_ok=True)
    os.makedirs("results/images", exist_ok=True)

    veh_info_csv = os.path.join("results", "vehiculinfo.csv")
    diagram_csv = os.path.join("results", "diagram.csv")
    image_root = os.path.join("results", "images")

    for idx, listing in enumerate(listings, start=1):
        print(f"Processing {idx}/{len(listings)} → {listing}")
        run(listing, veh_info_csv, diagram_csv, image_root)
        print("-" * 70)
