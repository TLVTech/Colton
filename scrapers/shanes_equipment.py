# scrapers/shanes_equipment.py
#  having issue with Pardon Our Interruption reCaptcha

import os
import re
import json
import csv
import time
import difflib
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
    raise RuntimeError("OPENAI_API_KEY not found in environment.")

#
# ── 1) Fuzzy‐matching helper
#
def find_most_relevant_option(input_value, options):
    """
    Return the single best fuzzy‐match from `options` for `input_value`.
    """
    if not input_value:
        return ""
    value = str(input_value).lower()
    best_match, best_score = "", 0.0
    for opt in options:
        score = difflib.SequenceMatcher(None, value, str(opt).lower()).ratio()
        if score > best_score:
            best_score, best_match = score, opt
    return best_match if best_score > 0.0 else ""


#
# ── 2) Write a dict (or list of dicts) to a CSV (append mode)
#
def writeToCSV(data, attributes, filename):
    """
    Append `data` (a dict or list‐of‐dicts) into `filename` as CSV rows.
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
# ── 3) Extract vehicle fields via ChatGPT
#
def extract_vehicle_info(text):
    """
    Ask ChatGPT to extract a fixed set of fields from `text`. Returns a dict or None.
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
The value of "OS - Vehicle Make" must be one of:
"Caterpillar", "Ford", "Freightliner", "GMC", "Hino", 
"International", "Kenworth", "Mack", "Peterbilt", "Sterling", "Volvo", "Western Star"
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
# ── 4) Coerce extracted fields into the proper types / allowed sets
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
        "Original info description": "text",
        "Origin": "text",
        # (We add OS - Vehicle Make here to enforce one of the allowed makes)
        "OS - Vehicle Make": "OS - Vehicle Make"
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
            opts = ["10 x 4","10 x 6","10 x 8","4 x 2","4 x 4","6 x 2","6 x 4","6 x 6","8 x 2","8 x 4","8 x 6","8 x 8"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Brake System Type":
            return find_most_relevant_option(v, ["Air", "Hydraulic"])

        if constraint == "OS - Engine Make":
            opts = ["Caterpillar","Chevrolet","Chrysler","Continental","Cummins","Detroit","Dodge",
                    "Duramax","Eaton","Ford","GMC","Hino","International","Isuzu","John Deere",
                    "Mack","Mercedes-Benz","Mitsubishi","Navistar","Nissan","PACCAR","Toyota","Volvo"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Fifth Wheel Type":
            return find_most_relevant_option(v, ["Fixed", "Sliding"])

        if constraint in ("OS - Front Suspension Type", "OS - Rear Suspension Type"):
            return find_most_relevant_option(v, ["Air Ride", "Spring"])

        if constraint == "OS - Fuel Type":
            opts = ["Bi-Fuel CNG","BioDiesel","Diesel","Electric","Gasoline","Hybrid Electric","Natural Gas","Propane"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Number of Front Axles":
            return 1  # always 1

        if constraint == "OS - Number of Fuel Tanks":
            return ""  # no data

        if constraint == "OS - Number of Rear Axles":
            return v  # we’ll override below if needed

        if constraint == "OS - Sleeper or Day Cab":
            return find_most_relevant_option(v, ["Day Cab", "Sleeper Cab"])

        if constraint == "OS - Transmission Make":
            opts = ["Aisin","Allison","Detroit","Eaton Fuller","Ford","GM","Mack","Mercedes-Benz",
                    "Mitsubishi","PACCAR","Rockwell","Spicer","Volvo"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Transmission Speeds":
            if v.isdigit():
                return f"{v}-speed"
            return find_most_relevant_option(v, [
                "2-speed","3-speed","4-speed","5-speed","6-speed","7-speed","8-speed","9-speed",
                "10-speed","12-speed","13-speed","15-speed","18-speed"
            ])

        if constraint == "OS - Transmission Type":
            return find_most_relevant_option(v, ["Automatic", "Manual"])

        if constraint == "OS - Vehicle Class":
            return "Class 8"

        if constraint == "OS - Vehicle Condition":
            return find_most_relevant_option(v, ["New", "Pre-Owned", "Used"])

        if constraint == "OS - Vehicle Make":
            opts = ["Caterpillar","Ford","Freightliner","GMC","Hino",
                    "International","Kenworth","Mack","Peterbilt","Sterling","Volvo","Western Star"]
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

        return v

    compliant = {}
    for field, constraint in field_constraints.items():
        raw = extracted_info.get(field, "")
        compliant[field] = convert_value(raw, constraint)

    # Derive OS - Number of Rear Axles from OS - Axle Configuration if needed
    cfg = compliant.get("OS - Axle Configuration", "")
    if cfg in ("4 x 2","4 x 4"):
        compliant["OS - Number of Rear Axles"] = 1
    elif cfg in ("6 x 2","6 x 4","6 x 6"):
        compliant["OS - Number of Rear Axles"] = 2
    elif cfg in ("8 x 4","8 x 6"):
        compliant["OS - Number of Rear Axles"] = 3
    elif cfg == "10 x 4":
        compliant["OS - Number of Rear Axles"] = 4

    # Ensure front‐suspension = rear‐suspension if one is blank
    fst = compliant.get("OS - Front Suspension Type", "")
    rst = compliant.get("OS - Rear Suspension Type", "")
    if fst and not rst:
        compliant["OS - Rear Suspension Type"] = fst
    if rst and not fst:
        compliant["OS - Front Suspension Type"] = rst

    # Set Not Active = 1 if empty
    if compliant.get("Not Active", "") == "":
        compliant["Not Active"] = 1

    # Unique id → always blank
    compliant["Unique id"] = ""

    return compliant


#
# ── 5) Selenium driver setup
#
def get_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    # Randomize UA slightly
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.54 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    opts.add_argument(f"user-agent={random.choice(uas)}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver


#
# ── 6) Record blocked URLs
#
def write_failed_url(url):
    with open("failed.txt", "a") as f:
        f.write(url + "\n")


#
# ── 7) Fetch a detail‐page’s text via Selenium → BeautifulSoup
#
def get_vehicle_page_html(url):
    """
    Load `url` with Selenium, wait for .detail-wrapper to appear, return its text.
    (No CAPTCHA‐handling beyond a basic pause‐and‐refresh.)
    """
    driver = None
    try:
        driver = get_driver()
        # random small delay before loading:
        time.sleep(random.uniform(2, 5))
        driver.get(url)

        # If blocked by CAPTCHA:
        if "Pardon Our Interruption" in driver.page_source:
            print("\nCAPTCHA detected at", url)
            print("Please solve it in the browser, then press Enter here...")
            input()
            time.sleep(3)
            driver.refresh()
            time.sleep(3)
            if "Pardon Our Interruption" in driver.page_source:
                print("Still blocked. Giving up on this URL.")
                write_failed_url(url)
                return ""

        # Human‐like scroll:
        def human_like_scroll():
            total_h = driver.execute_script("return document.body.scrollHeight")
            curr = 0
            step = random.randint(100, 300)
            while curr < total_h:
                nxt = min(curr + step, total_h)
                driver.execute_script(f"window.scrollTo({curr}, {nxt});")
                curr = nxt
                time.sleep(random.uniform(0.1, 0.3))

        time.sleep(random.uniform(3, 6))
        human_like_scroll()
        time.sleep(2)

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
# ── 8) Crawl “inventory” listing pages → collect all detail‐URLs
#
def get_target_listings():
    """
    Visit Shane’s Equipment inventory page, page through “Next” until done,
    collect every detail “href” under div#listContainer.
    Return a Python list of unique detail URLs (strings).
    """
    url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"
    inventory_prefix = "https://www.shanesequipment.com/inventory/"
    all_urls = set()
    driver = None

    try:
        driver = get_driver()
        print("Navigating to:", url)
        time.sleep(random.uniform(3, 6))
        driver.get(url)
        time.sleep(random.uniform(8, 12))

        # Optional: random mouse movement (if pyautogui installed)
        def random_mouse_movement():
            try:
                import pyautogui
                for _ in range(3):
                    x = random.randint(100, 1000)
                    y = random.randint(100, 600)
                    pyautogui.moveTo(x, y, duration=random.uniform(0.5, 1.0))
                    time.sleep(random.uniform(0.3, 0.6))
            except ImportError:
                pass

        random_mouse_movement()
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        if "Pardon Our Interruption" in driver.page_source:
            print("Blocked by CAPTCHA. Please solve it in the browser.")
            input("Press Enter after solving CAPTCHA...")
            driver.refresh()
            time.sleep(10)
            if "Pardon Our Interruption" in driver.page_source:
                print("Still blocked. Aborting.")
                return list(all_urls)

        try:
            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.ID, "listContainer"))
            )
            print("Found #listContainer")
        except TimeoutException:
            print("Could not find listContainer. Aborting.")
            return list(all_urls)

        while True:
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            lc = soup.find("div", id="listContainer")
            if lc:
                links = lc.find_all("a", href=True)
                for link in links:
                    href = link["href"]
                    if href.startswith("/"):
                        href = "https://www.shanesequipment.com" + href
                    if href.startswith(inventory_prefix):
                        all_urls.add(href)

                try:
                    next_btn = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Next Page']"))
                    )
                    # if it has a disabled class, we’re done
                    if "Mui-disabled" in next_btn.get_attribute("class"):
                        break
                    next_btn.click()
                    time.sleep(5)
                except Exception:
                    break
            else:
                break

    except WebDriverException as e:
        print("WebDriver error:", e)
    except Exception as e:
        print("General error:", e)
    finally:
        if driver:
            driver.quit()

    return list(all_urls)


#
# ── 9) Expose a flat `get_listings()` so that run_scraper.py can call it
#
def get_listings():
    return get_target_listings()


#
# ── 10) Given one detail URL, fetch text → extract fields → write CSV rows
#
def run(url, veh_info_csv, diagram_csv, image_folder):
    """
    1) Fetch detail‐page text via get_vehicle_page_html()
    2) Extract fields (extract_vehicle_info → make_extracted_info_compliant)
    3) Write one row into veh_info_csv; then build diagram row, write into diagram_csv.
    (No images are downloaded; image_folder is unused for Shane’s equipment.)
    """
    text = get_vehicle_page_html(url)
    if not text:
        print(f"[shanes_equipment] no text for {url}, skipping")
        return

    extracted = extract_vehicle_info(text)
    if not extracted:
        print(f"[shanes_equipment] GPT extraction failed for {url}, skipping")
        return

    extracted["Listing"] = url
    extracted["Original info description"] = text

    compliant = make_extracted_info_compliant(extracted)
    compliant["original_image_url"] = url

    # Write vehicle row
    writeToCSV(compliant, None, veh_info_csv)

    # Build diagram row (we reuse the same logic as other scrapers)
    diag = {"Listing": url}
    # We use the same complete_diagram_info as in the user’s provided code:
    diagram_info = {}
    cfg = compliant.get("OS - Axle Configuration", "")
    fields = []
    if cfg == "10 x 4":
        fields = ["F8", "F7", "R1", "R2"]
    elif cfg == "10 x 6":
        fields = ["F8", "F7", "R1", "R2", "R3"]
    elif cfg == "10 x 8":
        fields = ["F8", "F7", "F6", "R1", "R2"]
    elif cfg == "4 x 2":
        fields = ["F8", "R1"]
    elif cfg == "4 x 4":
        fields = ["F8", "R1"]
    elif cfg == "6 x 2":
        fields = ["F8", "R1"]
    elif cfg == "6 x 4":
        fields = ["F8", "R1", "R2"]
    elif cfg == "6 x 6":
        fields = ["F8", "R1", "R2"]
    elif cfg == "8 x 2":
        fields = ["F8", "F7", "R1"]
    elif cfg == "8 x 4":
        fields = ["F8", "F7", "R1", "R2"]
    elif cfg == "8 x 6":
        fields = ["F8", "R1", "R2", "R3"]
    elif cfg == "8 x 8":
        fields = ["F8", "F7", "R1", "R2"]

    out = {"Listing": url}
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

    writeToCSV(out, None, diagram_csv)
    print(f"[shanes_equipment] wrote data for {url}")


#
# ── 11) Quick‐test main (optional)
#
if __name__ == "__main__":
    urls = get_listings()
    print(f"Found {len(urls)} Shanes Equipment detail URLs.")
    if urls:
        os.makedirs("results", exist_ok=True)
        run(
            urls[0],
            "results/vehicleinfo.csv",
            "results/diagram.csv",
            "results/images"
        )
