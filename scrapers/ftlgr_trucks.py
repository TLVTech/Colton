"""
================================================================================
Colton Project – FTLGR Scraper
================================================================================
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
# import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# -- For JSON extraction ---
from core.output import write_to_csv
from core.normalization import complete_diagram_info
from core.image_utils import extract_image_urls_from_page, download_images as util_download_images, watermark_images
# -- For output fields ---
from core.output_fields import vehicle_attributes, diagram_attributes

# --- Disable SSL Warnings ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Load API key from environment ---
load_dotenv()
import openai
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Aborting.")


from seleniumwire import webdriver  # Use seleniumwire for proxy auth


def get_driver_with_brightdata_proxy():
    PROXY_HOST = os.environ.get("BRIGHTDATA_PROXY_HOST")
    PROXY_PORT = int(os.environ.get("BRIGHTDATA_PROXY_PORT"))
    PROXY_USER = os.environ.get("BRIGHTDATA_PROXY_USER")
    PROXY_PASS = os.environ.get("BRIGHTDATA_PROXY_PASS")

    seleniumwire_options = {
        'proxy': {
            'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'no_proxy': 'localhost,127.0.0.1'
        }
    }

    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # or just '--headless' if error persists
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)
    driver.set_page_load_timeout(120)
    return driver

# Utility to create Chrome proxy auth extension on the fly
def create_proxy_auth_extension(proxy_host, proxy_port, proxy_username, proxy_password):
    import zipfile, tempfile, os
    pluginfile = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """
    background_js = f"""
    var config = {{
            mode: "fixed_servers",
            rules: {{
              singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: parseInt({proxy_port})
              }},
              bypassList: ["localhost"]
            }}
          }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy_username}",
                password: "{proxy_password}"
            }}
        }};
    }}
    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """
    with zipfile.ZipFile(pluginfile.name, 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return pluginfile.name

# Helper function to find the most relevant option from a list based on similarity
def extract_json(raw):
    """
    Attempts to extract the first JSON object from a string (even if wrapped in ```).
    """
    try:
        # Remove code block markers if present
        cleaned = re.sub(r"^```json|^```|\s*```$", "", raw.strip())
        # Try to load directly
        return json.loads(cleaned)
    except Exception:
        # Fallback: try to extract with a regex
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                return {}
        return {}


def get_sleeper_listings():
    """
    Paginate through sleeper pages using Selenium (with Bright Data proxy) and collect truck URLs.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from urllib.parse import urljoin
    import time

    base_url = "https://www.ftlgr.com/trucks-for-sale/?type=sleeper"
    links = set()
    driver = get_driver_with_brightdata_proxy()  # Use proxy driver

    driver.get(base_url)
    page_num = 1

    while True:
        print(f"[Selenium] Scraping page {page_num}: {driver.current_url}")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.page-link"))
            )
        except Exception:
            print("[Selenium] Could not find page links—might be on last page.")

        # Collect truck links
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='/trucks/?vid=']"):
            href = a.get_attribute("href")
            full_url = urljoin("https://www.ftlgr.com", href)
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
        except Exception:
            print("[Selenium] No more pages or could not find Next button. Done paginating.")
            break

    driver.quit()
    print(f"[get_sleeper_listings] Total sleeper listings: {len(links)}")
    return list(links)


def get_daycab_listings():
    """
    Paginate through daycab pages using Selenium (with Bright Data proxy) and collect truck URLs.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from urllib.parse import urljoin
    import time

    base_url = "https://www.ftlgr.com/trucks-for-sale/?type=daycab"
    links = set()
    driver = get_driver_with_brightdata_proxy()  # Use proxy driver

    driver.get(base_url)
    page_num = 1

    while True:
        print(f"[Selenium] Scraping page {page_num}: {driver.current_url}")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.page-link"))
            )
        except Exception:
            print("[Selenium] Could not find page links—might be on last page.")

        # Collect truck links
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='/trucks/?vid=']"):
            href = a.get_attribute("href")
            full_url = urljoin("https://www.ftlgr.com", href)
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
        except Exception:
            print("[Selenium] No more pages or could not find Next button. Done paginating.")
            break

    driver.quit()
    print(f"[get_daycab_listings] Total daycab listings: {len(links)}")
    return list(links)


# ── Helper function to find the most relevant option based on similarity ─────────────
def find_most_relevant_option(input_value, options):
    best_match = None
    highest_score = 0

    for option in options:
        # Calculate similarity score
        score = difflib.SequenceMatcher(None, input_value, option).ratio()
        if score > highest_score:
            highest_score = score
            best_match = option

    return best_match


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

# ── Step 2: Fetch raw text for one “ftlgr” listing ───────────────────────────────
def get_vehicle_page_html(url: str) -> str:
    """
    Fetch the HTML from a single FTLGR listing and attempt to extract visible text.
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

        # Bright Data proxy config (from env)
        proxies = {
            "http": f"http://{os.environ['BRIGHTDATA_PROXY_USER']}:{os.environ['BRIGHTDATA_PROXY_PASS']}@{os.environ['BRIGHTDATA_PROXY_HOST']}:{os.environ['BRIGHTDATA_PROXY_PORT']}",
            "https": f"http://{os.environ['BRIGHTDATA_PROXY_USER']}:{os.environ['BRIGHTDATA_PROXY_PASS']}@{os.environ['BRIGHTDATA_PROXY_HOST']}:{os.environ['BRIGHTDATA_PROXY_PORT']}",
        }

        resp = session.get(url, headers=headers, allow_redirects=True, timeout=30, verify=False, proxies=proxies)
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
    # vehicle_fields = [
    #     "Company Address","ECM Miles","Engine Displacement","Engine Horsepower","Engine Hours",
    #     "Engine Model","Engine Serial Number","Engine Torque","Front Axle Capacity","Fuel Capacity",
    #     "glider","Listing","Location","Not Active","Odometer Miles","OS - Axle Configuration",
    #     "OS - Brake System Type","OS - Engine Make","OS - Fifth Wheel Type","OS - Front Suspension Type",
    #     "OS - Fuel Type","OS - Number of Front Axles","OS - Number of Fuel Tanks","OS - Number of Rear Axles",
    #     "OS - Rear Suspension Type","OS - Sleeper or Day Cab","OS - Transmission Make","OS - Transmission Speeds",
    #     "OS - Transmission Type","OS - Vehicle Class","OS - Vehicle Condition","OS - Vehicle Make",
    #     "OS - Vehicle Make Logo","OS - Vehicle Type","OS - Vehicle Year","Rear Axle Capacity","Rear Axle Ratio",
    #     "Ref Number","Stock Number","Transmission Model","U.S. State","U.S. State (text)",
    #     "Vehicle model - new","Vehicle Price","Vehicle Year","VehicleVIN","Wheelbase",
    #     "Original info description","original_image_url"
    # ]

    compliant["original_image_url"] = listing_url
    write_to_csv(compliant, vehicle_attributes, veh_info_csv)

    # 2) Write “diagram” CSV row
    diag_info = {"Listing": listing_url, "original_image_url": listing_url}
    # diag_fields = [
    #     "Listing","R1 Brake Type","R1 Dual Tires","R1 Lift Axle","R1 Power Axle","R1 Steer Axle",
    #     "R1 Tire Size","R1 Wheel Material","R2 Brake Type","R2 Dual Tires","R2 Lift Axle","R2 Power Axle",
    #     "R2 Steer Axle","R2 Tire Size","R2 Wheel Material","R3 Brake Type","R3 Dual Tires","R3 Lift Axle",
    #     "R3 Power Axle","R3 Steer Axle","R3 Tire Size","R3 Wheel Material","R4 Brake Type","R4 Dual Tires",
    #     "R4 Lift Axle","R4 Power Axle","R4 Steer Axle","R4 Tire Size","R4 Wheel Material","F5 Brake Type",
    #     "F5 Dual Tires","F5 Lift Axle","F5 Power Axle","F5 Steer Axle","F5 Tire Size","F5 Wheel Material",
    #     "F6 Brake Type","F6 Dual Tires","F6 Lift Axle","F6 Power Axle","F6 Steer Axle","F6 Tire Size",
    #     "F6 Wheel Material","F7 Brake Type","F7 Dual Tires","F7 Lift Axle","F7 Power Axle","F7 Steer Axle",
    #     "F7 Tire Size","F7 Wheel Material","F8 Brake Type","F8 Dual Tires","F8 Lift Axle","F8 Power Axle",
    #     "F8 Steer Axle","F8 Tire Size","F8 Wheel Material","original_image_url"
    # ]

    filled = complete_diagram_info({}, compliant)
    if not filled:
        filled = {}
    filled["Listing"] = listing_url
    write_to_csv(filled, diagram_attributes, diagram_csv)

    # 3) Download & watermark images (using utility function)
    stock = str(compliant.get("Stock Number", "")).strip()
    if stock:
        target = os.path.join(image_folder_root, stock)

        # USE THE DEALER ARGUMENT HERE!
        from core.image_utils import extract_image_urls_from_page, download_images, watermark_images

        # Get list of all image URLs using utility (set dealer="ftlgr" here)
        image_urls = extract_image_urls_from_page(listing_url, dealer="ftlgr")
        if not image_urls:
            print(f"[run] No image URLs found for {listing_url}")
        else:
            # Download all images to the target folder
            # downloaded_paths = download_images(image_urls, target)
            downloaded_paths = download_images(image_urls, target, dealer="ftlgr")
            # Watermark downloaded images into <target>-watermarked folder
            watermark_path = os.path.join("data", "raw", "group.png")
            watermarked_folder = f"{target}-watermarked"
            watermark_images(downloaded_paths, watermarked_folder, watermark_path)
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
        run(url, "results/vehicleinfo.csv", "results/diagram.csv", "results/images")
        print("-" * 70)
