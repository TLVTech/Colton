# fyda_freightliner.py

# having issues with scraping the vehicle info because of Verify the exact HTML/CSS on the real page

import os
import re
import json
import csv
import time
import difflib
import requests
import random

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import openai

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

#
# ── 0) Initialize OpenAI client from .env
#
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in the environment. Aborting.")

#
# ── 1) Utility: write a list of dicts (or single dict) to CSV
#
def writeToCSV(data, attributes, filename):
    """
    Append `data` (a dict or list-of-dicts) into `filename` as CSV rows.
    If `attributes` is None or empty, collect fieldnames from all keys in `data`.
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

    file_exists = os.path.exists(filename)
    file_empty = (not file_exists) or (os.path.getsize(filename) == 0)

    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=attributes)
        if file_empty:
            writer.writeheader()
        for row in data:
            out = {k: row.get(k, "") for k in attributes}
            writer.writerow(out)


#
# ── 2) Fuzzy‐matching helper
#
def find_most_relevant_option(input_value, options):
    """
    Return the single best fuzzy‐match from `options` for `input_value`.
    """
    if input_value is None:
        return ""
    value = str(input_value).lower()
    best_match, best_score = "", 0.0
    for opt in options:
        score = difflib.SequenceMatcher(None, value, str(opt).lower()).ratio()
        if score > best_score:
            best_score, best_match = score, opt
    return best_match if best_score > 0.0 else ""


#
# ── 3) Build the ChatGPT extraction prompt + parse JSON
#
def extract_vehicle_info(text):
    """
    Send `text` to OpenAI, asking it to extract all required fields.
    Returns a Python‐dict or None if parse failed.
    """
    messages = [
        {
            "role": "system",
            "content": """
You are a vehicle data extraction assistant.
Extract information from the text and return it in JSON with fields:
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
The field "Listing" should always be empty (we'll add it in code).
The field "Stock Number" appears as "Stock Number" in the text.
The field "OS - Vehicle Condition" appears as "Condition".
If text contains "sleep" or "sleeper" (case‐insensitive), choose "Sleeper Cab" for "OS - Sleeper or Day Cab"; otherwise "Day Cab".
The field "OS - Vehicle Year" appears as "Year".
The field "Vehicle Year" also appears as "Year".
The field "OS - Vehicle Make" appears as "Make".
The field "Vehicle model - new" appears as "Model".
Assume "Semi-tractor truck" for OS - Vehicle Type.
Assume "Class 8" for OS - Vehicle Class.
The "Ref Number" field should always be "".
The field "U.S. State" is found in the text as "Location"; extract the two-letter abbreviation and fully spell it out (same for "U.S. State (text)").
The field "Company Address" should always be "".
The field "ECM Miles" should always be "".
For OS - Fuel Type, assume "Diesel" unless "electric" appears, then "Electric".
The field "Fuel Capacity" should always be "".
When Transmission Model is "DT12", "DT-12", or "DT 12", set OS - Transmission Speeds = "12-speed" and OS - Transmission Type = "Automatic".
The field OS - Transmission Type appears as "Transmission" in text; if it is "AMT", use "Automatic".
The field "OS - Axle Configuration" appears as "Propulsion" in text.
Always set OS - Number of Front Axles = 1.
If OS - Axle Configuration is "4 x 2" or "4 x 4" → OS - Number of Rear Axles = 1;
If "6 x 2" / "6 x 4" / "6 x 6" → OS - Number of Rear Axles = 2;
If "8 x 4" / "8 x 6" → OS - Number of Rear Axles = 3;
If "10 x 4" → OS - Number of Rear Axles = 4.
OS - Front Suspension Type and OS - Rear Suspension Type should match; if one is empty, copy the other.
Set "Not Active" = 1.
The field "Unique id" should always be "".
"""
        },
        {"role": "user", "content": f"Extract vehicle information from this text: {text}"}
    ]

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        content = resp.choices[0].message.content
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print("Warning: failed to parse vehicle‐info JSON:", e)
        return None


#
# ── 4) Enforce field‐type / allowed‐value constraints
#
def make_extracted_info_compliant(extracted_info):
    """
    Coerce each field in `extracted_info` to the correct type or allowed set.
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
        "OS - Vehicle Year": "number",
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

    def convert_value(val, constraint):
        if val is None or str(val).strip() == "":
            return ""
        v = str(val).strip()

        if constraint == "number":
            nums = "".join(c for c in v if c.isdigit() or c == ".")
            try:
                return float(nums) if "." in nums else int(nums)
            except:
                return ""
        if constraint == "text":
            return v

        if constraint == "OS - yes/no":
            low = v.lower()
            return low if low in ("yes", "no") else ""

        if constraint == "OS - Axle Configuration":
            opts = ["10 x 4", "10 x 6", "10 x 8", "4 x 2", "4 x 4",
                    "6 x 2", "6 x 4", "6 x 6", "8 x 2", "8 x 4", "8 x 6", "8 x 8"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Brake System Type":
            return find_most_relevant_option(v, ["Air", "Hydraulic"])

        if constraint == "OS - Engine Make":
            opts = ["Caterpillar", "Chevrolet", "Chrysler", "Continental", "Cummins",
                    "Detroit", "Dodge", "Duramax", "Eaton", "Ford", "GMC", "Hino",
                    "International", "Isuzu", "John Deere", "Mack", "Mercedes-Benz",
                    "Mitsubishi", "Navistar", "Nissan", "PACCAR", "Toyota", "Volvo"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Fifth Wheel Type":
            return find_most_relevant_option(v, ["Fixed", "Sliding"])

        if constraint in ("OS - Front Suspension Type", "OS - Rear Suspension Type"):
            return find_most_relevant_option(v, ["Air Ride", "Spring"])

        if constraint == "OS - Fuel Type":
            opts = ["Bi-Fuel CNG", "BioDiesel", "Diesel", "Electric", "Gasoline",
                    "Hybrid Electric", "Natural Gas", "Propane"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Number of Front Axles":
            return 1  # Always 1

        if constraint == "OS - Number of Fuel Tanks":
            return ""  # no data, leave blank

        if constraint == "OS - Number of Rear Axles":
            return v  # temporarily return raw; override below

        if constraint == "OS - Sleeper or Day Cab":
            return find_most_relevant_option(v, ["Day Cab", "Sleeper Cab"])

        if constraint == "OS - Transmission Make":
            opts = ["Aisin", "Allison", "Detroit", "Eaton Fuller", "Ford", "GM", "Mack",
                    "Mercedes-Benz", "Mitsubishi", "PACCAR", "Rockwell", "Spicer", "Volvo"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Transmission Speeds":
            if v.isdigit():
                return f"{v}-speed"
            return find_most_relevant_option(v, ["2-speed","3-speed","4-speed","5-speed","6-speed",
                                                 "7-speed","8-speed","9-speed","10-speed","12-speed",
                                                 "13-speed","15-speed","18-speed"])

        if constraint == "OS - Transmission Type":
            return find_most_relevant_option(v, ["Automatic", "Manual"])

        if constraint == "OS - Vehicle Class":
            return "Class 8"

        if constraint == "OS - Vehicle Condition":
            return find_most_relevant_option(v, ["New", "Pre-Owned", "Used"])

        if constraint == "OS - Vehicle Make":
            opts = ["Caterpillar","Chevrolet","Freightliner","GMC","Hino","International",
                    "Kenworth","Mack","Peterbilt","Volvo","Western Star"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Vehicle Type":
            return "Semi-tractor truck"

        if constraint == "OS - Vehicle Year":
            try:
                return int(v)
            except:
                return ""

        if constraint == "OS - State":
            mapping = {
                "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
                "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
                "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas",
                "KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
                "MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana",
                "NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico",
                "NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma",
                "OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota",
                "TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
                "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
            }
            key = v.upper()
            return mapping.get(key, find_most_relevant_option(v, list(mapping.values())))

        if constraint == "OS - Number of Rear Axles":
            return v  # will override later

        return v

    compliant = {}
    for field, constraint in field_constraints.items():
        raw = extracted_info.get(field, "")
        compliant[field] = convert_value(raw, constraint)

    # Derive OS - Number of Rear Axles from OS - Axle Configuration if needed
    cfg = compliant.get("OS - Axle Configuration", "")
    if cfg in ("4 x 2", "4 x 4"):
        compliant["OS - Number of Rear Axles"] = 1
    elif cfg in ("6 x 2", "6 x 4", "6 x 6"):
        compliant["OS - Number of Rear Axles"] = 2
    elif cfg in ("8 x 4", "8 x 6"):
        compliant["OS - Number of Rear Axles"] = 3
    elif cfg == "10 x 4":
        compliant["OS - Number of Rear Axles"] = 4

    # Ensure OS - Front Suspension Type = OS - Rear Suspension Type if one is blank
    fst = compliant.get("OS - Front Suspension Type", "")
    rst = compliant.get("OS - Rear Suspension Type", "")
    if fst and not rst:
        compliant["OS - Rear Suspension Type"] = fst
    if rst and not fst:
        compliant["OS - Front Suspension Type"] = rst

    # Set Not Active = 1 if it was empty
    if compliant.get("Not Active", "") == "":
        compliant["Not Active"] = 1

    # Unique id → always blank
    compliant["Unique id"] = ""

    return compliant


#
# ── 5) Selenium driver setup (for pages behind JS / CAPTCHA)
#
def get_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    # Randomize UA slightly
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.6943.54 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.6943.54 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    ]
    opts.add_argument(f"user-agent={random.choice(uas)}")

    # Automatically manage the ChromeDriver binary
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver


#
# ── 6) Write blocked URLs
#
def write_failed_url(url):
    with open("failed.txt", "a") as f:
        f.write(url + "\n")


#
# ── 7) Given a detail‐page URL, fetch its visible text via Selenium/BeautifulSoup
#
def get_vehicle_page_html(url):
    """
    Load `url` with Selenium, wait for .detail-wrapper to appear, and return its text.
    Handle CAPTCHA page titled "Pardon Our Interruption" by pausing for manual solve.
    """
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(5)

        # If we hit CAPTCHA block:
        if "Pardon Our Interruption" in driver.page_source:
            print("\nCAPTCHA detected at", url)
            print("Please solve it in the browser window, then press Enter here…")
            input()
            time.sleep(5)
            driver.refresh()
            time.sleep(5)
            if "Pardon Our Interruption" in driver.page_source:
                print("Still blocked after CAPTCHA. Giving up on this URL.")
                write_failed_url(url)
                return ""

        # Scroll to bottom to load lazy content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Wait for .detail-wrapper to appear
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "detail-wrapper"))
            )
        except TimeoutException:
            print("detail-wrapper not found on", url)
            return ""

        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        wrapper = soup.find("div", class_="detail-wrapper")
        return wrapper.get_text(separator=" ", strip=True) if wrapper else ""
    except Exception as e:
        print("Error in get_vehicle_page_html:", e)
        return ""
    finally:
        if driver:
            driver.quit()


#
# ── 8) For each “category” URL (inventory index), collect all detail‐page URLs
#
def get_target_listings(category_url):
    """
    Load one “category” page (e.g. “day cab”, “sleeper”, etc.).  Collect all <div class="vehicle_row"> → <a href="…">
    and paginate by clicking “next” (id="next2") until done.  Returns (list_of_detail_URLs, list_of_raw_texts).
    We only need URLs for our pipeline; we drop the raw text here.
    """
    base = "https://www.fydafreightliner.com"
    all_urls = []
    all_texts = []
    driver = None

    try:
        driver = get_driver()
        driver.get(category_url)
        time.sleep(7)

        while True:
            # Scroll down to load any lazy items
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='vehicle_row']"))
            )
            soup = BeautifulSoup(driver.page_source, "html.parser")
            rows = soup.find_all("div", class_=lambda c: c and "vehicle_row" in c)

            for r in rows:
                a = r.find("a", href=True)
                text = r.get_text(separator=" ", strip=True)
                if a:
                    href = a["href"]
                    if href.startswith("/"):
                        href = base + href
                    elif not href.startswith("http"):
                        href = base + "/" + href
                    all_urls.append(href)
                    all_texts.append(text)
                else:
                    all_urls.append("")
                    all_texts.append(text)

            # Try clicking “Next” (id=next2)
            try:
                nxt = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "next2"))
                )
                if nxt.get_attribute("disabled"):
                    break
                nxt.click()
                time.sleep(8)
            except TimeoutException:
                break
            except Exception:
                break

        return all_urls, all_texts
    except WebDriverException as e:
        print("WebDriver error:", e)
        return [], []
    finally:
        if driver:
            driver.quit()


#
# ── 9) Expose a flat “get_listings()” for pipeline/run_scraper.py
#
def get_listings():
    """
    Combine all category URLs into one flat list of detail‐page URLs.
    """
    category_urls = [
        "https://www.fydafreightliner.com/--xallinventory?gad_source=1&gclid=…#page=xallinventory&vc=cab%20%26%20chassis",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=cab%20%26%20chassis%20trucks",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=conventional%20day%20cab%20trucks",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=conventional%20trucks%20w%2F%20sleeper",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=conventional%20trucks%20w%2Fo%20sleeper",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=conventional%20with%20sleeper",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=conventional%20without%20sleeper",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=day%20cab",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=day%20cab%20tractors",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=on%20highway",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=other",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=sleeper%20tractors",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=tractor",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=tri-drive",
        "https://www.fydafreightliner.com/--xallinventory?…&vc=truck",
    ]

    all_details = []
    for cu in category_urls:
        urls, _ = get_target_listings(cu)
        all_details.extend(urls)

    # Remove duplicates while preserving order
    seen = set()
    final = []
    for u in all_details:
        if u and (u not in seen):
            seen.add(u)
            final.append(u)

    return final


#
# ── 10) Diagram‐row defaults (same style as Jasper/Five_Star)
#
def complete_diagram_info(diagram_info, compliant_info):
    """
    Given a partly‐filled diagram_info (must have "Listing"), plus the compliant_info dict,
    return a new dict with all "R1 Dual Tires", "R1 Lift Axle", etc. fields initialized.
    """
    config = compliant_info.get("OS - Axle Configuration", "")
    fields = []
    if config == "10 x 4":
        fields = ["F8", "F7", "R1", "R2"]
    elif config == "10 x 6":
        fields = ["F8", "F7", "R1", "R2", "R3"]
    elif config == "10 x 8":
        fields = ["F8", "F7", "F6", "R1", "R2"]
    elif config == "4 x 2":
        fields = ["F8", "R1"]
    elif config == "4 x 4":
        fields = ["F8", "R1"]
    elif config == "6 x 2":
        fields = ["F8", "R1"]
    elif config == "6 x 4":
        fields = ["F8", "R1", "R2"]
    elif config == "6 x 6":
        fields = ["F8", "R1", "R2"]
    elif config == "8 x 2":
        fields = ["F8", "F7", "R1"]
    elif config == "8 x 4":
        fields = ["F8", "F7", "R1", "R2"]
    elif config == "8 x 6":
        fields = ["F8", "R1", "R2", "R3"]
    elif config == "8 x 8":
        fields = ["F8", "F7", "R1", "R2"]

    out = {"Listing": diagram_info.get("Listing", "")}
    for f in fields:
        out[f + " Dual Tires"] = ""
        out[f + " Lift Axle"] = ""
        out[f + " Power Axle"] = ""
        out[f + " Steer Axle"] = ""
        out[f + " Tire Size"] = ""
        out[f + " Wheel Material"] = ""

    # Fill R1 defaults
    if "R1 Dual Tires" in out:
        out["R1 Dual Tires"] = "yes"
    if "R1 Lift Axle" in out:
        out["R1 Lift Axle"] = "no"
    if "R1 Power Axle" in out:
        out["R1 Power Axle"] = "yes"
    if "R1 Steer Axle" in out:
        out["R1 Steer Axle"] = "no"

    return out


#
# ── 11) The “run” function for one detail‐page URL
#
def run(url, veh_info_csv, diagram_csv, image_folder):
    """
    1) Fetch text of detail page (via get_vehicle_page_html)
    2) Extract fields with extract_vehicle_info → make_extracted_info_compliant
    3) Write one row into veh_info_csv (plus "original_image_url"=url)
    4) Build diagram row and write into diagram_csv
    (No image-download for FYDA—just write CSVs.)
    """
    text = get_vehicle_page_html(url)
    if not text:
        print(f"[fyda] no text for {url}, skipping.")
        return

    extracted = extract_vehicle_info(text)
    if not extracted:
        print(f"[fyda] GPT extraction failed for {url}, skipping.")
        return

    extracted["Listing"] = url
    extracted["Original info description"] = text

    compliant = make_extracted_info_compliant(extracted)
    compliant["original_image_url"] = url

    # Write vehicle row
    writeToCSV(compliant, None, veh_info_csv)

    # Build & write diagram row
    diag = {"Listing": url}
    diag_filled = complete_diagram_info(diag, compliant)
    writeToCSV(diag_filled, None, diagram_csv)

    print(f"[fyda] Wrote data for {url}")


#
# If you ever want to run this module by itself for a quick smoke-test:
#
if __name__ == "__main__":
    listings = get_listings()
    print(f"Found {len(listings)} FYDA detail URLs.")
    # Just process the first one as a quick test:
    if listings:
        os.makedirs("results", exist_ok=True)
        run(
            listings[0],
            "results/vehicleinfo.csv",
            "results/diagram.csv",
            "results/images"
        )
