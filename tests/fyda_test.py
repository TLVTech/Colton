import os
import sys
import time
import requests

# -- Ensure project modules are discoverable
sys.path.insert(0, os.path.abspath("."))

from scrapers.fyda_freightliner import (
    get_target_listings,
    get_vehicle_page_html,
    extract_vehicle_info,
    make_extracted_info_compliant,
    complete_diagram_info,
    writeToCSV,
)
from core.watermark import add_watermark

# --- SETTINGS ---
WATERMARK_PATH = "data/raw/group.png"
IMAGES_RAW_DIR = "results/images/fyda_raw"
IMAGES_WM_DIR = "results/images/fyda"
RESULTS_DIR = "results"
VEH_CSV = os.path.join(RESULTS_DIR, "vehicleinfo.csv")
DIAG_CSV = os.path.join(RESULTS_DIR, "diagram.csv")


def download_images_from_fyda(detail_url, dest_folder, page_html=None):
    """
    Scrapes images from FYDA truck detail page — now handles background-image divs.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    import re

    chrome_opts = webdriver.ChromeOptions()
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    driver.set_page_load_timeout(30)

    os.makedirs(dest_folder, exist_ok=True)
    img_urls = []
    try:
        driver.get(detail_url)
        time.sleep(5)

        # Find divs with background-image
        bg_divs = driver.find_elements(By.CSS_SELECTOR, "div.background-image")
        for div in bg_divs:
            style = div.get_attribute("style")
            if style:
                match = re.search(r'background-image:\s*url\((.*?)\)', style)
                if match:
                    img_url = match.group(1).strip('\'"')
                    img_urls.append(img_url)

        print(f"Found {len(img_urls)} truck images in background-image divs.")

        # Download images
        saved = []
        for idx, url in enumerate(set(img_urls), 1):
            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
            fname = os.path.join(dest_folder, f"fyda_{idx}{ext}")
            try:
                r = requests.get(url, timeout=10)
                with open(fname, "wb") as f:
                    f.write(r.content)
                saved.append(fname)
                print(f"Downloaded {url} -> {fname}")
            except Exception as e:
                print(f"Failed to download {url}: {e}")
        driver.quit()
        return saved
    except Exception as e:
        print("Error (download_images_from_fyda):", e)
        try: driver.quit()
        except: pass
        return []
    """
    Downloads gallery images from a truck detail page.
    Filters out logos and icons.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    chrome_opts = webdriver.ChromeOptions()
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    driver.set_page_load_timeout(30)

    os.makedirs(dest_folder, exist_ok=True)
    img_urls = []

    try:
        driver.get(detail_url)
        time.sleep(5)

        # Try targeted selectors for gallery images
        img_elems = driver.find_elements(By.CSS_SELECTOR, "div.galleryImages img")
        if not img_elems:
            img_elems = driver.find_elements(By.CSS_SELECTOR, "div.slick-slide img")
        if not img_elems:
            img_elems = driver.find_elements(By.TAG_NAME, "img")

        for img in img_elems:
            src = img.get_attribute("src")
            if (
                src
                and src.startswith("http")
                and ("inventory" in src or "trucks" in src)
                and not src.lower().endswith(".svg")
            ):
                img_urls.append(src)

        print(f"Found {len(img_urls)} images in gallery.")

        saved = []
        for idx, url in enumerate(set(img_urls), 1):
            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
            fname = os.path.join(dest_folder, f"fyda_{idx}{ext}")
            try:
                r = requests.get(url, timeout=10)
                with open(fname, "wb") as f:
                    f.write(r.content)
                saved.append(fname)
                print(f"Downloaded {url} -> {fname}")
            except Exception as e:
                print(f"Failed to download {url}: {e}")
        return saved

    except Exception as e:
        print("Error (download_images_from_fyda):", e)
        return []

    finally:
        try:
            driver.quit()
        except:
            pass


def watermark_images(input_files, output_dir, watermark_path):
    os.makedirs(output_dir, exist_ok=True)
    for f in input_files:
        try:
            fname = os.path.basename(f)
            outpath = os.path.join(output_dir, fname)
            add_watermark(f, watermark_path, outpath)
            print(f"Watermarked {f} -> {outpath}")
        except Exception as e:
            print(f"Failed to watermark {f}: {e}")


def test_fyda_full_flow():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Step 1: Get truck detail URLs (test with first one)
    category_url = (
        "https://www.fydafreightliner.com/commercial-trucks-vans-for-sale-ky-oh-pa--xNewInventory"
        "#page=xNewInventory&vc=sleeper"
    )
    detail_urls, _ = get_target_listings(category_url)
    if not detail_urls:
        print("No detail URLs found!")
        return

    url = detail_urls[0]
    print(f"\nTesting with: {url}\n")

    # Step 2: Extract vehicle page HTML
    html = get_vehicle_page_html(url)
    if not html:
        print("Failed to get vehicle HTML/text.")
        return

    # Step 3: Extract vehicle info using OpenAI
    extracted = extract_vehicle_info(html)
    if not extracted:
        print("OpenAI extraction failed.")
        return
    extracted["Listing"] = url
    extracted["Original info description"] = html

    compliant = make_extracted_info_compliant(extracted)
    compliant["original_image_url"] = url

    # Step 4: Write vehicle info to CSV
    writeToCSV(compliant, None, VEH_CSV)

    # Step 5: Write diagram row
    diag = {"Listing": url}
    diag_filled = complete_diagram_info(diag, compliant)
    writeToCSV(diag_filled, None, DIAG_CSV)
    print(f"Vehicle info/diagram rows written for {url}")

    # Step 6: Download truck images
    downloaded_files = download_images_from_fyda(url, IMAGES_RAW_DIR)
    if not downloaded_files:
        print("No truck images downloaded, skipping watermark step.")
        return

    # Step 7: Watermark images
    watermark_images(downloaded_files, IMAGES_WM_DIR, WATERMARK_PATH)
    print("Watermarking done.")


if __name__ == "__main__":
    test_fyda_full_flow()
    print("\nFYDA full test complete.")
