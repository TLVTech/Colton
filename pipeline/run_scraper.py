# pipeline/run_scraper.py

import os
import argparse

from scrapers.jasper_trucks import get_target_listings as get_jasper_listings, run as run_jasper
from scrapers.five_star_trucks import get_listings as get_five_star_listings, run as run_five_star
from scrapers.ftlgr_trucks import get_listings as get_ftlgr_listings, run as run_ftlgr
from scrapers.fyda_freightliner import get_listings as get_fyda_listings, run as run_fyda
from scrapers.shanes_equipment import get_listings as get_shanes_listings, run as run_shanes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run one or more scrapers: jasper, five_star, ftlgr, fyda, shanes_equipment, or all."
    )
    parser.add_argument(
        "--source", "-s",
        choices=["jasper", "five_star", "ftlgr", "fyda", "shanes_equipment", "all"],
        default="all",
        help="Which scraper to run: jasper, five_star, ftlgr, fyda, shanes_equipment, or all."
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=None,
        help="(Optional) Only scrape the first N results from each selected source."
    )
    args = parser.parse_args()

    # Build a combined list of (source_name, url) tuples
    urls = []

    # ── Jasper
    if args.source in ("jasper", "all"):
        jasper = get_jasper_listings()
        if args.limit is not None:
            jasper = jasper[: args.limit]
        print(f"[run_scraper] Adding {len(jasper)} Jasper URLs.")
        urls.extend([("jasper", u) for u in jasper])

    # ── Five Star
    if args.source in ("five_star", "all"):
        five_star = get_five_star_listings()
        if args.limit is not None:
            five_star = five_star[: args.limit]
        print(f"[run_scraper] Adding {len(five_star)} 5 Star URLs.")
        urls.extend([("five_star", u) for u in five_star])

    # ── FTGLR
    if args.source in ("ftlgr", "all"):
        ftlgr = get_ftlgr_listings()
        if args.limit is not None:
            ftlgr = ftlgr[: args.limit]
        print(f"[run_scraper] Adding {len(ftlgr)} FTLGR URLs.")
        urls.extend([("ftlgr", u) for u in ftlgr])

    # ── FYDA Freightliner
    if args.source in ("fyda", "all"):
        fyda = get_fyda_listings(limit=args.limit)
        print(f"[run_scraper] Adding {len(fyda)} FYDA URLs.")
        urls.extend([("fyda", u) for u in fyda])

    # ── Shanes Equipment
    if args.source in ("shanes_equipment", "all"):
        shanes = get_shanes_listings()
        if args.limit is not None:
            shanes = shanes[: args.limit]
        print(f"[run_scraper] Adding {len(shanes)} Shanes Equipment URLs.")
        urls.extend([("shanes_equipment", u) for u in shanes])

    print(f"[run_scraper] Total URLs to process: {len(urls)}")

    # Ensure output directories exist
    os.makedirs("results", exist_ok=True)
    os.makedirs("results/images", exist_ok=True)

    veh_info_csv = os.path.join("results", "vehiculinfo.csv")
    diagram_csv  = os.path.join("results", "diagram.csv")
    image_root   = os.path.join("results", "images")

    for idx, (source, url) in enumerate(urls, start=1):
        print(f"[run_scraper] {idx}/{len(urls)} ({source}) → {url}")
        if source == "jasper":
            run_jasper(url, veh_info_csv, diagram_csv, image_root)
        elif source == "five_star":
            run_five_star(url, veh_info_csv, diagram_csv, image_root)
        elif source == "ftlgr":
            run_ftlgr(url, veh_info_csv, diagram_csv, image_root)
        elif source == "fyda":
            run_fyda(url, veh_info_csv, diagram_csv, image_root)
        elif source == "shanes_equipment":
            run_shanes(url, veh_info_csv, diagram_csv, image_root)
        print("-" * 60)

    print("[run_scraper] Done.")
