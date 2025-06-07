# tests/fyda_selenium_test.py

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def get_target_listings_via_selenium(category_url, max_pages=10):
    """
    Load category_url (e.g. the 'sleeper' inventory) with Selenium,
    wait for .vehicle_row elements, collect all <a href="…"> inside each,
    then click “Next” until no more pages (or max_pages), and return a list
    of absolute detail‐page URLs.
    """
    chrome_opts = webdriver.ChromeOptions()
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    # If you want to run in headless mode (no browser window), uncomment below:
    # chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    driver.set_page_load_timeout(30)

    all_urls = []
    try:
        driver.get(category_url)
        # Give the page a few seconds to run its initial JavaScript
        time.sleep(5)

        for page_num in range(1, max_pages + 1):
            try:
                # Wait until at least one <div class="vehicle_row"> appears
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.vehicle_row"))
                )
            except Exception:
                print(f"[selenium] No .vehicle_row found on page {page_num}, stopping.")
                break

            # Scroll down to force any lazy‐loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Grab all the <div class="vehicle_row"> elements on this page
            rows = driver.find_elements(By.CSS_SELECTOR, "div.vehicle_row")
            if not rows:
                print(f"[selenium] Zero .vehicle_row elements on page {page_num}.")
                break

            for r in rows:
                try:
                    link = r.find_element(By.TAG_NAME, "a")
                    href = link.get_attribute("href")
                    if href:
                        # Turn relative URLs into absolute
                        if href.startswith("/"):
                            href = "https://www.fydafreightliner.com" + href
                        all_urls.append(href)
                except Exception:
                    # If there’s no <a> or some error, skip it
                    continue

            print(f"[selenium] Page {page_num}: found {len(rows)} rows, "
                  f"{len(all_urls)} total URLs so far.")

            # Try to click the “Next” button
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.pageButton.next")
                # If it’s disabled, break out
                if next_btn.get_attribute("disabled") or not next_btn.is_enabled():
                    print("[selenium] Next button is disabled → last page reached.")
                    break

                next_btn.click()
                time.sleep(5)  # wait for JS to load the next set of rows
            except Exception:
                print("[selenium] Could not click Next button (last page?).")
                break

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for u in all_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    finally:
        driver.quit()


if __name__ == "__main__":
    sleeper_url = (
        "https://www.fydafreightliner.com/"
        "commercial-trucks-vans-for-sale-ky-oh-pa--xNewInventory"
        "#page=xNewInventory&vc=sleeper"
    )
    urls = get_target_listings_via_selenium(sleeper_url)
    print("\n=== Final detail URLs found:", len(urls), "===\n")
    for idx, u in enumerate(urls, 1):
        print(f"{idx:>2}. {u}")
