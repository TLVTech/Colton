# pipeline/run_scraper.py
import sys
import os
import argparse
import subprocess

# Ensure correct encoding for wide character support in logs
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Import all available scrapers here
from scrapers.jasper_trucks import get_target_listings as get_jasper_listings, run as run_jasper
from scrapers.five_star_trucks import get_listings as get_five_star_listings, run as run_five_star
from scrapers.ftlgr_trucks import get_listings as get_ftlgr_listings, run as run_ftlgr
from scrapers.fyda_freightliner import get_listings as get_fyda_listings, run as run_fyda
from scrapers.shanes_equipment import get_listings as get_shanes_listings, run as run_shanes

# Available scrapers dictionary for dynamic selection
SCRAPERS = {
    "jasper":        (get_jasper_listings, run_jasper),
    "five_star":     (get_five_star_listings, run_five_star),
    "ftlgr":         (get_ftlgr_listings, run_ftlgr),
    "fyda":          (get_fyda_listings, run_fyda),
    "shanes_equipment": (get_shanes_listings, run_shanes)
}

def main():
    parser = argparse.ArgumentParser(
        description="Run any combination of scrapers (jasper, five_star, ftlgr, fyda, shanes_equipment), or ALL."
    )
    parser.add_argument(
        "--source", "-s",
        nargs="+",
        choices=list(SCRAPERS.keys()) + ["all"],
        default=["all"],
        help="Which scraper(s) to run (space-separated): jasper, five_star, ftlgr, fyda, shanes_equipment, or all."
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=None,
        help="(Optional) Only scrape the first N results from each selected source."
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run reconciliation and zipping after scraping."
    )
    args = parser.parse_args()

    # --- Determine which scrapers to run
    sources = args.source
    if "all" in sources:
        sources = list(SCRAPERS.keys())

    # --- Ensure output directories exist
    os.makedirs("results", exist_ok=True)
    os.makedirs("results/images", exist_ok=True)

    veh_info_csv = os.path.join("results", "vehicleinfo.csv")
    diagram_csv  = os.path.join("results", "diagram.csv")
    image_root   = os.path.join("results", "images")

    # --- Loop through selected scrapers
    for source in sources:
        get_listings_func, run_func = SCRAPERS[source]
        urls = get_listings_func()
        if args.limit is not None:
            urls = urls[: args.limit]
        print(f"[run_scraper] Running '{source}' with {len(urls)} URLs.")
        for idx, url in enumerate(urls, start=1):
            print(f"[{source}] {idx}/{len(urls)} => {url}")
            run_func(url, veh_info_csv, diagram_csv, image_root)
        print("-" * 60)

    print("[run_scraper] Done with all selected scrapers.")

    # --- Optionally run reconciliation and zipping
    if args.full:
        print("[run_scraper] Running reconciliation step...")
        try:
            subprocess.run([sys.executable, "-m", "pipeline.run_reconciliation"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"!! Error in reconciliation: {e}")
        print("[run_scraper] Running zipping step...")
        try:
            subprocess.run([sys.executable, "-m", "pipeline.zip_only"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"!! Error in zipping: {e}")
        print("[run_scraper] Full pipeline complete.")

if __name__ == "__main__":
    main()
