# Colton_Project (Jasper‐Trucks Scraper & Pipeline)

This repository contains everything needed to scrape JasperTrucks inventory pages, extract vehicle data with OpenAI, download images, watermark them, and then reconcile into final CSVs.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Quick Start](#quick-start)
5. [Pipeline Steps](#pipeline-steps)
   - [Run Scraper](#run-scraper)
   - [Run Reconciliation](#run-reconciliation)
   - [Zip Outputs](#zip-outputs)
6. [Project Structure](#project-structure)
7. [Requirements](#requirements)

---

## Prerequisites

- Python 3.11 or above
- (Linux/macOS) `zip` command if you want to test the shell‐zip approach; otherwise, Python’s `shutil` is used by default.

---

## Installation

1. Clone this repo:
   ```bash
   git clone https://github.com/yourusername/Colton_Project.git
   cd Colton_Project/colton
   ```

````

2. Create a virtual environment and activate it:

   ```bash
   python3 -m venv .venv
   source .venv/Scripts/activate     # on Windows (Git Bash)
   # source .venv/bin/activate       # on macOS/Linux
   ```

3. Install dependencies:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Configuration

1. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env          # Git Bash / WSL / macOS / Linux
   # or on Windows cmd: copy .env.example .env
   ```

2. Edit `.env` and paste your real OpenAI API key:

   ```
   OPENAI_API_KEY=sk-<your-actual-key-here>
   ```

---

## Quick Start

Once everything is installed and your `.env` is in place, you can run the entire pipeline with one command:

```bash
chmod +x run_all.sh
./run_all.sh
```

That will:

1. Run the scraper (`pipeline/run_scraper.py`)
2. Run the reconciliation (`pipeline/run_reconciliation.py`)
3. Zip up both `results/` and `myresults/` into a file named `results_Jasper_YYYY-MM-DD_coltonmkt.zip`

---

## Pipeline Steps

### Run Scraper

```bash
python pipeline/run_scraper.py
```

* Produces:

  * `results/diagram.csv`
  * `results/vehiculinfo.csv`
  * `results/images/<stock_no>/...` and corresponding `-watermarked/` folders

### Run Reconciliation

```bash
python pipeline/run_reconciliation.py
```

* Reads from `results/…`, writes to `myresults/`:

  * `myresults/diagram_data.csv`
  * `myresults/vehicle_info.csv`

### Zip Outputs

If you only want to bundle the outputs without re-running the scraper, you can run:

```bash
python zip_results.py    # or use the `run_all.sh` logic
```

That will create `results_Jasper_<date>_coltonmkt.zip` in the project root, containing:

```
results/
├── diagram.csv
├── vehiculinfo.csv
└── images/…

myresults/
├── diagram_data.csv
└── vehicle_info.csv
```

---

## Project Structure

```
.
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
├── run_all.sh
├── run_all.py
├── test_openai.py
├── test_smoke.py
├── debug_import.py

├── config/
│   ├── dealers.yaml
│   └── prompts/

├── core/
│   ├── __init__.py
│   ├── normalization.py
│   ├── output.py
│   ├── reconciliation.py
│   ├── utils.py
│   └── watermark.py

├── pipeline/
│   ├── __init__.py
│   ├── download_data.py
│   ├── run_scraper.py
│   ├── run_reconciliation.py
│   └── run_all.py (Python driver, if you have it)

├── scrapers/
│   ├── __init__.py
│   ├── jasper_trucks.py
│   ├── jasper_run_scraper.py
│   ├── fyda_run_scraper.py
│   └── fydafreightlinerV2.py

├── tests/
│   └── test_reconciliation.py

├── data/
│   ├── raw/
│   │   └── group.png
│   ├── exports/
│   └── bubble_exports/
```

Anything under `results/` and `myresults/` is ignored by Git (they are automatically generated, so they should not be checked in).

---

## Requirements

Your `requirements.txt` should pin each dependency your code needs. For example:

```
beautifulsoup4==4.13.4
brotli==1.1.0
cairosvg==2.8.2
gdown==5.2.0
openai==0.28.0
Pillow==11.2.1
pandas==2.2.3
requests==2.32.3
urllib3==2.4.0
```

If you have any other packages used in `core/` or `pipeline/` (e.g. `python-dateutil`, `lxml`, etc.), add them here too.

After updating `requirements.txt`, anyone can do:

```bash
pip install -r requirements.txt
```

to reproduce your environment exactly.

---

## 6. Final sanity check before you push

1. Confirm `git status` only shows uncommitted changes for files you actually want to track. Example:

   ```bash
   git status
   # On branch main
   # Untracked files:
   #   (use "git add <file>..." to include in what will be committed)
   #
   #   .env.example
   #   pipeline/run_all.py  ← if you created it
   #
   # nothing added to commit but untracked files present (use "git add" to track)
   ```

   You should *not* see `results/`, `myresults/`, or `.env`.

2. If you accidentally have committed your real `.env`, remove it:

   ```bash
   git rm --cached .env
   echo ".env" >> .gitignore
   git commit -m "Remove .env from tracking"
   ```

3. Make sure you have added and committed:

   * `.gitignore`
   * `.env.example`
   * `README.md`
   * `requirements.txt`
   * all your source‐code folders (`scrapers/`, `pipeline/`, `core/`, `config/`, `tests/`)
   * `run_all.sh` (or `run_all.py`), `test_openai.py`, etc.

4. Push to GitHub:

   ```bash
   git add .
   git commit -m "Prepare project for GitHub: ignore generated files, add README + .env.example"
   git push origin main
   ```

---
````
