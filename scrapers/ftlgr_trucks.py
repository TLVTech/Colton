"""
================================================================================
Colton Project – FTLGR Scraper: Selenium/Requests/Cloudflare Anti-Bot Advisory
================================================================================

Summary of Changes & Findings
-----------------------------
• Tested multiple approaches for scraping https://www.ftlgr.com/trucks-for-sale/:
    1. Requests with browser-like headers (403 Forbidden – blocked by Cloudflare).
    2. Selenium with undetected-chromedriver (headless and visible mode).
    3. Selector and page structure debugging.
• Confirmed site is protected by Cloudflare’s advanced bot detection:
    - All automation tools (Selenium, Playwright) are blocked.
    - Browser automation, even in non-headless mode, is denied access.
    - Manual browser access works, but automated tools are consistently blocked.
• Results: No truck listing links can be scraped programmatically using standard methods.

Options Considered
------------------
A. Manual Cookie Injection: Tried, but Cloudflare protection quickly invalidates cookies/sessions.
B. Residential Proxies: Viable for large-scale and persistent scraping, but requires paid proxy service.
C. API/Data Vendor: Not available for this dealer, but ideal if possible.
D. Manual Export: Possible for small-scale or demo runs, not scalable.
E. Cloud Browser/Proxy Service (e.g. ScraperAPI, ScrapingBee): Can work, but requires a paid plan.

Next Steps
----------
-> **Best solution:** Integrate a residential or rotating proxy service in conjunction with Selenium, Playwright, or requests.
    - This is the only scalable approach for Cloudflare-protected automotive dealer sites.
    - Most production-grade automotive data vendors use this method.
-> Until proxy integration is complete, test pipeline with manually pasted listing URLs if necessary.

"""



import os
import json
import re
import difflib
import time
import csv
import requests
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- For Selenium browser automation ---
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Disable SSL Warnings ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Load API key from environment ---
load_dotenv()
import openai
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Aborting.")

# ----- STEP 1: Collect all FTLGR URLs (Selenium-powered) -----

def get_sleeper_listings():
    """
    Paginate through sleeper pages using Selenium (undetected-chromedriver) and collect truck URLs.
    """
    base_url = "https://www.ftlgr.com/trucks-for-sale/?type=sleeper"
    links = set()
    options = uc.ChromeOptions()
    options.headless = False  # Set to False for debugging
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    driver.get(base_url)
    page_num = 1

    while True:
        print(f"[Selenium] Scraping page {page_num}: {driver.current_url}")
        # Wait until page loaded, then grab listing links
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.page-link"))
            )
        except Exception:
            print("[Selenium] Could not find page links—might be on last page.")

        # Collect truck links
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='/trucks/?vid=']"):
            full_url = "https://www.ftlgr.com" + a.get_attribute("href")
            links.add(full_url)

        # Try to click "Next" (not disabled)
        try:
            next_btn = driver.find_element(
                By.XPATH,
                "//a[contains(@class,'page-link') and contains(text(),'Next') and not(ancestor::li[contains(@class,'disabled')])]"
            )
            next_btn.click()
            time.sleep(2)
            page_num += 1
        except Exception as e:
            print("[Selenium] No more pages or could not find Next button. Done paginating.")
            break

    driver.quit()
    print(f"[get_sleeper_listings] Total sleeper listings: {len(links)}")
    return list(links)

def get_daycab_listings():
    """
    Paginate through daycab pages using Selenium and collect truck URLs.
    """
    base_url = "https://www.ftlgr.com/trucks-for-sale/?type=daycab"
    links = set()
    options = uc.ChromeOptions()
    options.headless = True  # Set to False for debugging
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    driver.get(base_url)
    page_num = 1

    while True:
        print(f"[Selenium] Scraping page {page_num}: {driver.current_url}")
        # Wait until page loaded, then grab listing links
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.page-link"))
            )
        except Exception:
            print("[Selenium] Could not find page links—might be on last page.")

        # Collect truck links
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='/trucks/?vid=']"):
            full_url = "https://www.ftlgr.com" + a.get_attribute("href")
            links.add(full_url)

        # Try to click "Next" (not disabled)
        try:
            next_btn = driver.find_element(
                By.XPATH,
                "//a[contains(@class,'page-link') and contains(text(),'Next') and not(ancestor::li[contains(@class,'disabled')])]"
            )
            next_btn.click()
            time.sleep(2)
            page_num += 1
        except Exception as e:
            print("[Selenium] No more pages or could not find Next button. Done paginating.")
            break

    driver.quit()
    print(f"[get_daycab_listings] Total daycab listings: {len(links)}")
    return list(links)

def get_listings():
    """
    Return a combined list of sleeper + daycab listing URLs.
    """
    all_listings = set()

    print("\n[get_listings] Fetching sleeper listings...")
    sleeper = get_sleeper_listings()
    all_listings.update(sleeper)
    print(f"[get_listings] {len(sleeper)} sleeper listings.\n")

    print("[get_listings] Fetching daycab listings...")
    daycab = get_daycab_listings()
    all_listings.update(daycab)
    print(f"[get_listings] {len(daycab)} daycab listings.\n")

    print(f"[get_listings] Total unique listings: {len(all_listings)}\n")
    return list(all_listings)

# ── CSV Writer ──────────────────────────────────────────────────────────────────
def writeToCSV(data, attributes, filename):
    """
    Append a list of dicts (or a single dict) to CSV `filename`. If `filename`
    does not exist or is empty, write a header row first.
    """
    if isinstance(data, dict):
        data = [data]

    if not attributes:
        attrs = set()
        for row in data:
            attrs.update(row.keys())
        attributes = sorted(attrs)

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_empty = not os.path.exists(filename) or os.path.getsize(filename) == 0

    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=attributes)
        if file_empty:
            writer.writeheader()
        for row in data:
            out_row = {attr: row.get(attr, "") for attr in attributes}
            writer.writerow(out_row)


# ── Step 2: Fetch raw text for one “ftlgr” listing ───────────────────────────────
def get_vehicle_page_html(url: str) -> str:
    """
    Fetch the HTML from a single FTLGR listing and attempt to extract visible text.
    We look for known container classes/IDs first; if nothing is found, we fall back
    to body text with header/footer removed.
    """
    try:
        session = requests.Session()
        headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.ftlgr.com/",
    "Origin": "https://www.ftlgr.com",
}
        resp = session.get(url, headers=headers, allow_redirects=True, timeout=30, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        text_content = ""

        # Try common “vehicle detail” selectors first:
        selectors = [
            ("main", {"role": "main"}),
            ("div", {"class": "vehicle-detail"}),
            ("div", {"class": "listing-detail"}),
            ("div", {"class": "vehicle-description"}),
            ("div", {"id": "vehicle-info"}),
            ("div", {"class": "content-area"}),
        ]
        for tag, attrs in selectors:
            element = soup.find(tag, attrs)
            if element:
                text_content += element.get_text(separator=" ", strip=True) + "\n"
        # If still empty, try any <section> or <div> whose class name contains 'vehicle', 'truck', 'detail', 'spec', or 'info'
        if not text_content.strip():
            for section in soup.find_all(["section", "div"], class_=lambda x: x and any(
                term in str(x).lower() for term in ("vehicle", "truck", "detail", "spec", "info"))):
                text_content += section.get_text(separator=" ", strip=True) + "\n"
        # If still no content, strip entire <body> (minus header/footer/nav)
        if not text_content.strip():
            body = soup.find("body")
            if body:
                for rem in body.find_all(["header", "footer", "nav"]):
                    rem.decompose()
                text_content = body.get_text(separator=" ", strip=True)

        return text_content.strip()

    except Exception as e:
        print(f"[get_vehicle_page_html] Error fetching {url}: {e}")
        return ""


# ── Step 3: Use OpenAI to extract JSON from raw text ──────────────────────────────
def extract_vehicle_info(text: str) -> dict:
    """
    Send `text` to OpenAI ChatCompletion with a system prompt to produce a JSON dict
    of all required truck fields. Returns None on failure.
    """
    system_msg = {
        "role": "system",
        "content": """
You are a vehicle data extraction assistant.
Extract information from the text and return it in a JSON format with these fields:
Company Address, ECM Miles, Engine Displacement, Engine Horsepower, Engine Hours,
Engine Model, Engine Serial Number, Engine Torque, Front Axle Capacity, Fuel Capacity,
glider, Listing, Location, Not Active, Odometer Miles, OS - Axle Configuration,
OS - Brake System Type, OS - Engine Make, OS - Fifth Wheel Type, OS - Front Suspension Type,
OS - Fuel Type, OS - Number of Front Axles, OS - Number of Fuel Tanks, OS - Number of Rear Axles,
OS - Rear Suspension Type, OS - Sleeper or Day Cab, OS - Transmission Make, OS - Transmission Speeds,
OS - Transmission Type, OS - Vehicle Class, OS - Vehicle Condition, OS - Vehicle Make,
OS - Vehicle Make Logo, OS - Vehicle Type, OS - Vehicle Year, Rear Axle Capacity,
Rear Axle Ratio, Ref Number, Stock Number, Transmission Model, U.S. State,
U.S. State (text), Vehicle model - new, Vehicle Price, Vehicle Year, VehicleVIN,
Wheelbase.
If a field is not found, leave it empty.
By default, OS - Vehicle Condition = “Pre-Owned” unless Odometer Miles < 100 -> “New.”
If “Axle” label = “TANDEM” -> OS - Axle Configuration = “6 x 4.”
If “Axle” label = “SINGLE” -> OS - Axle Configuration = “4 x 2.”
Assume “Diesel” for OS - Fuel Type.
If Axle=“TANDEM,” OS - Number of Front Axles = 1 and OS - Number of Rear Axles = 2.
If Axle=“SINGLE,” OS - Number of Front Axles = 1 and OS - Number of Rear Axles = 1.
If Axle is empty, default OS - Axle Configuration = “6 x 4.” ECM Miles always blank.
If Engine Model contains Engine Make, strip out the duplicate make. 
Select the grey number followed by “Miles” -> Odometer Miles.
Select “Sleeper Cab” for OS - Sleeper or Day Cab unless paragraph under Stock # contains “Day” -> “Day Cab.”
Assume “Class 8” for OS - Vehicle Class and “Semi-tractor truck” for OS - Vehicle Type.
Select “Vehicle model — new” based on the page title.
Fields “Listing,” “Company Address,” and “Engine Displacement” always empty.
Field “Not Active” = 1.
If OS - Front Suspension Type is empty but OS - Rear Suspension Type is present (or vice-versa), copy over the non-empty value.
If “Eaton” appears under Transmission Make, use “Eaton Fuller.”
If “auto” or “Auto” appears under Transmission Type, replace with “Automatic.”
“Ref Number” always empty.
“Stock Number” lives right after “Stock #” in text (alphanumeric OK).
Just above the phone number is “City, ST.” Use the ST abbreviation to set both “U.S. State” and “U.S. State (text).”
        """
    }
    user_msg = {"role": "user", "content": f"Extract vehicle information from this text: {text}"}

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[system_msg, user_msg],
            temperature=0.1,
            max_tokens=1000
        )
        raw = resp.choices[0].message.content
        print("[extract_vehicle_info] Raw GPT->JSON (first 200 chars):", raw[:200].replace("\n", " ") + " …")
        # Try parsing out the JSON object:
        cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback to regex‐extraction
            obj = extract_json(cleaned)
            return obj or {}
    except Exception as e:
        print(f"[extract_vehicle_info] OpenAI error: {e}")
        return {}


# ── Step 4: Enforce field constraints ───────────────────────────────────────────────
def make_extracted_info_compliant(extracted_info: dict) -> dict:
    """
    Given a raw dict from GPT, coerce each field into the expected type or allowable value.
    """
    field_constraints = {
        "Company Address": "text",
        "ECM Miles": "number",
        "Engine Displacement": "number",
        "Engine Horsepower": "number",
        "Engine Hours": "number",
        "Engine Model": "text",
        "Engine Serial Number": "text",
        "Engine Torque": "text",
        "Front Axle Capacity": "number",
        "Fuel Capacity": "number",
        "glider": "OS - yes/no",
        "Listing": "text",
        "Location": "text",
        "Not Active": "number",
        "Odometer Miles": "number",
        "OS - Axle Configuration": "OS - Axle Configuration",
        "OS - Brake System Type": "OS - Brake System Type",
        "OS - Engine Make": "OS - Engine Make",
        "OS - Fifth Wheel Type": "OS - Fifth Wheel Type",
        "OS - Front Suspension Type": "OS - Front Suspension Type",
        "OS - Fuel Type": "OS - Fuel Type",
        "OS - Number of Front Axles": "OS - Number of Front Axles",
        "OS - Number of Fuel Tanks": "OS - Number of Fuel Tanks",
        "OS - Number of Rear Axles": "OS - Number of Rear Axles",
        "OS - Rear Suspension Type": "OS - Rear Suspension Type",
        "OS - Sleeper or Day Cab": "OS - Sleeper or Day Cab",
        "OS - Transmission Make": "OS - Transmission Make",
        "OS - Transmission Speeds": "OS - Transmission Speeds",
        "OS - Transmission Type": "OS - Transmission Type",
        "OS - Vehicle Class": "OS - Vehicle Class",
        "OS - Vehicle Condition": "OS - Vehicle Condition",
        "OS - Vehicle Make": "OS - Vehicle Make",
        "OS - Vehicle Make Logo": "text",
        "OS - Vehicle Type": "OS - Vehicle Type",
        "OS - Vehicle Year": "text",
        "Rear Axle Capacity": "number",
        "Rear Axle Ratio": "number",
        "Ref Number": "text",
        "Stock Number": "text",
        "Transmission Model": "text",
        "U.S. State": "OS - State",
        "U.S. State (text)": "text",
        "Vehicle model - new": "OS - Vehicle Model",
        "Vehicle Price": "number",
        "Vehicle Year": "number",
        "VehicleVIN": "text",
        "Wheelbase": "number",
        "Unique id": "text",
        "Original info description": "text"
    }

    def convert_value(value, constraint):
        if value is None or value == "":
            return ""
        val_str = str(value).strip()
        if constraint == "number":
            try:
                cleaned = "".join(c for c in val_str if c.isdigit() or c == ".")
                return float(cleaned) if "." in cleaned else int(cleaned)
            except:
                return ""
        if constraint == "text":
            return val_str
        if constraint == "OS - yes/no":
            low = val_str.lower()
            return low if low in ("yes", "no") else ""
        if constraint == "OS - Axle Configuration":
            opts = ["10 x 4","10 x 6","10 x 8","4 x 2","4 x 4","6 x 2","6 x 4","6 x 6","8 x 2","8 x 4","8 x 6","8 x 8"]
            return find_most_relevant_option(val_str, opts)
        if constraint == "OS - Brake System Type":
            return find_most_relevant_option(val_str, ["Air", "Hydraulic"])
        if constraint == "OS - Engine Make":
            return find_most_relevant_option(val_str, [
                "Caterpillar", "Freightliner","Kenworth","Peterbilt","Volvo","Mack","International","Hino","Sterling","GMC","Ford","Western Star","Other"
            ])
        if constraint == "OS - Vehicle Model":
            # (You could list known models here; for brevity, we just return the raw string)
            return val_str
        if constraint == "OS - State":
            mapping = {
                "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
                "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
                "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
                "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
                "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi",
                "MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire",
                "NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina",
                "ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania",
                "RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee",
                "TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
                "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
            }
            up = val_str.upper()
            if up in mapping:
                return mapping[up]
            return find_most_relevant_option(val_str, list(mapping.values()))
        if constraint == "OS - Sleeper or Day Cab":
            return find_most_relevant_option(val_str, ["Day Cab", "Sleeper Cab"])
        if constraint == "OS - Vehicle Make Logo":
            return val_str
        if constraint == "OS - Fifth Wheel Type":
            return find_most_relevant_option(val_str, ["Fixed", "Sliding"])
        if constraint in ("OS - Front Suspension Type", "OS - Rear Suspension Type"):
            return find_most_relevant_option(val_str, ["Air Ride", "Spring"])
        if constraint == "OS - Transmission Make":
            alt = find_most_relevant_option(val_str, [
                "Aisin","Allison","Detroit","Eaton Fuller","Mack","Volvo","Meritor","PACCAR","Rockwell","Spicer","Torqshift","Mitsubishi"
            ])
            return "Eaton Fuller" if val_str.lower()=="eaton" else alt
        if constraint == "OS - Transmission Speeds":
            if val_str.isdigit():
                return f"{val_str}-speed"
            return ""
        if constraint == "OS - Transmission Type":
            alt = find_most_relevant_option(val_str, ["Automatic","Manual"])
            return alt if alt else "Automatic"
        if constraint == "OS - Vehicle Condition":
            alt = find_most_relevant_option(val_str, ["New","Pre-Owned","Used"])
            return "Pre-Owned" if alt=="Used" else alt
        if constraint == "OS - Vehicle Type":
            return "Semi-tractor truck"
        if constraint == "OS - Vehicle Class":
            return "Class 8"
        if constraint == "OS - Fuel Type":
            return "Diesel"
        if constraint in ("OS - Number of Front Axles","OS - Number of Rear Axles","OS - Number of Fuel Tanks"):
            # if we get a numeric-like string, just return that integer
            if val_str.isdigit():
                return int(val_str)
            return ""
        return val_str

    compliant = {}
    for fld, cst in field_constraints.items():
        v = extracted_info.get(fld, "")
        compliant[fld] = convert_value(v, cst)
    return compliant


# ── Step 5: Download all FTLGR images ────────────────────────────────────────────
def download_images(url: str, folder_name: str) -> None:
    """
    Given a listing URL, find the main image (.mainimage) + any .carousel‐item/thumb images.
    Save them to folder_name/ as main_image.jpg, 1.jpg, 2.jpg, etc.
    """
    os.makedirs(folder_name, exist_ok=True)
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) main image
    main_img = soup.find("img", class_="mainimage")
    if main_img and main_img.get("src") and not main_img["src"].startswith("data:"):
        href = urljoin(url, main_img["src"])
        try:
            r2 = requests.get(href)
            r2.raise_for_status()
            with open(os.path.join(folder_name, "main_image.jpg"), "wb") as f:
                f.write(r2.content)
            print(f"[download_images] Downloaded main_image.jpg")
        except Exception as e:
            print(f"[download_images] Error downloading main image: {e}")

    # 2) carousel items
    car_items = soup.find_all("div", class_="carousel-item")
    print(f"[download_images] Found {len(car_items)} carousel items")
    for idx, c in enumerate(car_items, start=1):
        img = c.find("img", class_="thumb")
        if not img or not img.get("src"):
            continue
        thumb_url = img["src"]
        full_url = thumb_url.replace("/TH_", "/")
        full_url = urljoin(url, full_url)
        try:
            r3 = requests.get(full_url)
            r3.raise_for_status()
            ext = os.path.splitext(full_url)[1].lower() or ".jpg"
            outname = os.path.join(folder_name, f"{idx}{ext}")
            with open(outname, "wb") as f:
                f.write(r3.content)
            print(f"[download_images] Downloaded {os.path.basename(outname)}")
        except Exception as e:
            print(f"[download_images] Error downloading {full_url}: {e}")

    print("[download_images] Done.")


# ── Step 6: run() orchestrator ───────────────────────────────────────────────────
def run(
    listing_url: str,
    veh_info_csv: str,
    diagram_csv: str,
    image_folder_root: str,
) -> None:
    """
    1. Fetch raw text (get_vehicle_page_html)
    2. extract with OpenAI -> make_extracted_info_compliant
    3. Write both vehicle CSV row + diagram CSV row
    4. Download all images under image_folder_root/<Stock Number>/
    5. Watermark each image (group.png assumed at data/raw/group.png)
    """
    vehicle_text = get_vehicle_page_html(listing_url)
    if not vehicle_text:
        print(f"[run] No text for {listing_url}; skipping.")
        return

    extracted = extract_vehicle_info(vehicle_text)
    if not isinstance(extracted, dict):
        print(f"[run] Extraction returned non‐dict for {listing_url}; skipping.")
        return

    extracted["Original info description"] = vehicle_text
    compliant = make_extracted_info_compliant(extracted)

    # Ensure results folders exist
    os.makedirs(os.path.dirname(veh_info_csv), exist_ok=True)
    os.makedirs(os.path.dirname(diagram_csv), exist_ok=True)

    # 1) Write “vehicle” CSV row
    vehicle_fields = [
        "Company Address","ECM Miles","Engine Displacement","Engine Horsepower","Engine Hours",
        "Engine Model","Engine Serial Number","Engine Torque","Front Axle Capacity","Fuel Capacity",
        "glider","Listing","Location","Not Active","Odometer Miles","OS - Axle Configuration",
        "OS - Brake System Type","OS - Engine Make","OS - Fifth Wheel Type","OS - Front Suspension Type",
        "OS - Fuel Type","OS - Number of Front Axles","OS - Number of Fuel Tanks","OS - Number of Rear Axles",
        "OS - Rear Suspension Type","OS - Sleeper or Day Cab","OS - Transmission Make","OS - Transmission Speeds",
        "OS - Transmission Type","OS - Vehicle Class","OS - Vehicle Condition","OS - Vehicle Make",
        "OS - Vehicle Make Logo","OS - Vehicle Type","OS - Vehicle Year","Rear Axle Capacity","Rear Axle Ratio",
        "Ref Number","Stock Number","Transmission Model","U.S. State","U.S. State (text)",
        "Vehicle model - new","Vehicle Price","Vehicle Year","VehicleVIN","Wheelbase",
        "Original info description","original_image_url"
    ]
    compliant["original_image_url"] = listing_url
    writeToCSV(compliant, vehicle_fields, veh_info_csv)

    # 2) Write “diagram” CSV row
    diag_info = {"Listing": listing_url, "original_image_url": listing_url}
    diag_fields = [
        "Listing","R1 Brake Type","R1 Dual Tires","R1 Lift Axle","R1 Power Axle","R1 Steer Axle",
        "R1 Tire Size","R1 Wheel Material","R2 Brake Type","R2 Dual Tires","R2 Lift Axle","R2 Power Axle",
        "R2 Steer Axle","R2 Tire Size","R2 Wheel Material","R3 Brake Type","R3 Dual Tires","R3 Lift Axle",
        "R3 Power Axle","R3 Steer Axle","R3 Tire Size","R3 Wheel Material","R4 Brake Type","R4 Dual Tires",
        "R4 Lift Axle","R4 Power Axle","R4 Steer Axle","R4 Tire Size","R4 Wheel Material","F5 Brake Type",
        "F5 Dual Tires","F5 Lift Axle","F5 Power Axle","F5 Steer Axle","F5 Tire Size","F5 Wheel Material",
        "F6 Brake Type","F6 Dual Tires","F6 Lift Axle","F6 Power Axle","F6 Steer Axle","F6 Tire Size",
        "F6 Wheel Material","F7 Brake Type","F7 Dual Tires","F7 Lift Axle","F7 Power Axle","F7 Steer Axle",
        "F7 Tire Size","F7 Wheel Material","F8 Brake Type","F8 Dual Tires","F8 Lift Axle","F8 Power Axle",
        "F8 Steer Axle","F8 Tire Size","F8 Wheel Material","original_image_url"
    ]
    filled = complete_diagram_info({}, compliant)
    filled["Listing"] = listing_url
    writeToCSV(filled, diag_fields, diagram_csv)

    # 3) Download & watermark images
    stock = str(compliant.get("Stock Number", "")).strip()
    if stock:
        target = os.path.join(image_folder_root, stock)
        download_images(listing_url, target)

        from core.watermark import process_folder_watermark
        watermark_path = os.path.join("data", "raw", "group.png")
        processtarget = f"{target}-watermarked"
        process_folder_watermark(target, processtarget, watermark_path)
    else:
        print(f"[run] No Stock Number for {listing_url}; skipping images.")


# ── If you ever want a “standalone test” in this file ─────────────────────────────
if __name__ == "__main__":
    listings = get_listings()
    print(f"[__main__] Will process {len(listings)} listings.")
    for idx, url in enumerate(listings, start=1):
        print(f"[__main__] {idx}/{len(listings)} -> {url}")
        os.makedirs("results", exist_ok=True)
        os.makedirs("results/images", exist_ok=True)
        run(url, "results/vehiculinfo.csv", "results/diagram.csv", "results/images")
        print("-" * 70)
