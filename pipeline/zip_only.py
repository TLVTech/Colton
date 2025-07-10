#!/usr/bin/env python3
"""
zip_only.py

Packages both "results/" and "myresults/" directories into a single date-stamped ZIP.

Usage:
    python zip_only.py
    python zip_only.py --output jasper_results_2025-07-09_coltonmkt.zip

It uses the SCRAPER_NAME env variable if available for the filename.
"""

import os
import sys
import zipfile
from datetime import datetime

def zip_folder(zip_file: zipfile.ZipFile, folder_path: str, arc_root: str) -> None:
    """
    Walk through `folder_path` and add all files/subfolders under it into `zip_file`.
    Each entry in the ZIP will be stored under the subdirectory named `arc_root`.
    """
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            abs_path = os.path.join(root, f)
            rel_path = os.path.relpath(abs_path, folder_path)
            arc_name = os.path.join(arc_root, rel_path)
            zip_file.write(abs_path, arc_name)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zips results/ and myresults/ folders")
    parser.add_argument("--output", help="Output ZIP file name", default=None)
    args = parser.parse_args()

    # Get SCRAPER_NAME from env if available
    scraper_name = os.environ.get("SCRAPER_NAME", "scrapers")

    # Today's date string
    today = datetime.now().strftime("%Y-%m-%d")

    # Compute output ZIP name
    zip_filename = args.output or f"{scraper_name}_results_{today}_coltonmkt.zip"

    # Check both folders
    if not os.path.isdir("results"):
        print("Error: ./results/ folder not found. Nothing to zip.")
        sys.exit(1)
    if not os.path.isdir("myresults"):
        print("Error: ./myresults/ folder not found. Nothing to zip.")
        sys.exit(1)

    print(f"-> Creating ZIP file: {zip_filename}")
    with zipfile.ZipFile(zip_filename, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        print("   -> Adding 'results/' …")
        zip_folder(zf, "results", arc_root="results")
        print("   -> Adding 'myresults/' …")
        zip_folder(zf, "myresults", arc_root="myresults")

    print(f"Done. Created `{zip_filename}` in the project root.")

if __name__ == "__main__":
    main()
