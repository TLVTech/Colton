import sys
import subprocess
import os

# Always ensure working directory is project root (one level up from 'pipeline')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# You can enable/disable any scraper here
SCRAPERS = [
    {"name": "five_star", "check": True},
    {"name": "jasper",    "check": True},
    {"name": "fyda",      "check": True},
    {"name": "ftlgr",     "check": False},
    {"name": "shanes",    "check": False},
]

def run_scraper(scraper_name):
    try:
        print(f"\n=== RUNNING SCRAPER: {scraper_name} ===")
        subprocess.run([sys.executable, "-m", "pipeline.run_scraper", "--source", scraper_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"!! Error running scraper {scraper_name}: {e}")

def main():
    for scraper in SCRAPERS:
        if scraper["check"]:
            run_scraper(scraper["name"])

    print("\n=== RUNNING RECONCILIATION ===")
    try:
        subprocess.run([sys.executable, "-m", "pipeline.run_reconciliation"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"!! Error in reconciliation: {e}")

    print("\n=== CREATING ZIP ARCHIVE ===")
    try:
        subprocess.run([sys.executable, "-m", "pipeline.zip_only"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"!! Error in zipping: {e}")

if __name__ == "__main__":
    main()
