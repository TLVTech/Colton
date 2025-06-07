#!/usr/bin/env python3
"""
zip_only.py

Packages both "results/" and "myresults/" directories into a single date-stamped ZIP.

Usage:
    python zip_only.py

After it finishes, you should see a file like
    results_Jasper_2025-06-05_coltonmkt.zip
in your project root.
"""

import os
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
            # Build the archive name: drop everything up to `folder_path`
            rel_path = os.path.relpath(abs_path, folder_path)
            arc_name = os.path.join(arc_root, rel_path)
            zip_file.write(abs_path, arc_name)

def main():
    # 1) Figure out today's date string:
    today = datetime.now().strftime("%Y-%m-%d")

    # 2) Name of our output ZIP file:
    zip_filename = f"results_Jasper_{today}_coltonmkt.zip"

    # 3) Check that “results/” and “myresults/” both exist
    if not os.path.isdir("results"):
        print("Error: ./results/ folder not found. Nothing to zip.")
        return
    if not os.path.isdir("myresults"):
        print("Error: ./myresults/ folder not found. Nothing to zip.")
        return

    # 4) Create the ZIP file in “w”rite mode
    print(f"→ Creating ZIP file: {zip_filename}")
    with zipfile.ZipFile(zip_filename, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 4a) zip up everything under results/
        print("   → Adding 'results/' …")
        zip_folder(zf, "results", arc_root="results")

        # 4b) zip up everything under myresults/
        print("   → Adding 'myresults/' …")
        zip_folder(zf, "myresults", arc_root="myresults")

    print(f"✔ Done. Created `{zip_filename}` in the project root.")

if __name__ == "__main__":
    main()
