# tests/test_ftlgr.py

import os
from scrapers.ftlgr_trucks import get_listings, run

def test_ftlgr_scraper():
    # Prepare output paths (in a temp or test folder to avoid clobbering prod results)
    veh_info_csv = "results/test_vehiculinfo.csv"
    diagram_csv = "results/test_diagram.csv"
    image_root = "results/test_images"

    # Get a short list of test URLs
    urls = get_listings()
    test_urls = urls[:3]  # Limit to 3 for quick testing

    # Clean up old test files if present
    for f in [veh_info_csv, diagram_csv]:
        if os.path.exists(f):
            os.remove(f)
    if os.path.isdir(image_root):
        import shutil
        shutil.rmtree(image_root)

    # Run the scraper on each test URL
    for idx, url in enumerate(test_urls, 1):
        print(f"Testing FTLGR scraper on URL {idx}: {url}")
        run(url, veh_info_csv, diagram_csv, image_root)

    print("Test complete. Check results in 'results/test_vehiculinfo.csv', 'results/test_diagram.csv', and 'results/test_images/'.")

if __name__ == "__main__":
    test_ftlgr_scraper()
