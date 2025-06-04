#!/usr/bin/env python3
import os
import sys
import subprocess
import zipfile
from datetime import date

def main():
    # 1) Make sure we're running from the project root (where run_all.py lives)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 2) (Optional) Ensure PYTHONPATH points to “.” so that `scrapers/` etc. are importable.
    #    In almost all cases, simply running "python run_all.py" from the repo root
    #    is enough (Python will see '' in sys.path). If you have trouble, uncomment below:
    #
    # os.environ["PYTHONPATH"] = script_dir

    # 3) Check for OPENAI_API_KEY (the scraper code calls load_dotenv() at runtime).
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY is not set in the environment. "
              "run_all.py will still attempt to run, but 'scrapers' may fail.\n"
              "Either put a valid key into a '.env' file or export it in your shell before calling this script.\n")
    else:
        print("→ OPENAI_API_KEY found.\n")

    # 4) Run the scraper
    print("→ Running scraper…")
    try:
        subprocess.run(
            [sys.executable, "pipeline/run_scraper.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: 'run_scraper.py' failed with exit code {e.returncode}")
        sys.exit(1)

    # 5) Run the reconciliation
    print("\n→ Running reconciliation…")
    try:
        subprocess.run(
            [sys.executable, "pipeline/run_reconciliation.py"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: 'run_reconciliation.py' failed with exit code {e.returncode}")
        sys.exit(1)

    # 6) Zip up “results/” + “myresults/” into a single archive
    mydate = date.today().strftime("%Y-%m-%d")
    zip_name = f"results_Jasper_{mydate}_coltonmkt.zip"
    print(f"\n→ Zipping up “results/” + “myresults/” → {zip_name}")

    directories_to_zip = ["results", "myresults"]
    with zipfile.ZipFile(zip_name, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder in directories_to_zip:
            if not os.path.isdir(folder):
                print(f"Warning: directory '{folder}/' not found; skipping it.")
                continue

            for root, dirs, files in os.walk(folder):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    # arcname should be relative, so that zip root contains "results/..." and "myresults/..."
                    arcname = os.path.relpath(filepath, start=script_dir)
                    zf.write(filepath, arcname)
    print(f"\nDone. Created: {zip_name}\n")

if __name__ == "__main__":
    main()
