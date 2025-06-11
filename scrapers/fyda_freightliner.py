# fyda_freightliner.py

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

# watermark function (fallback if missing)
try:
    from core.watermark import add_watermark
except ImportError:
    print("Warning: core.watermark not found → skipping watermarking.")
    def add_watermark(input_path, watermark_path, output_path):
        print(f"Skipped watermark: {input_path}")

# --------------------------------------------------
# 0) Initialize OpenAI client from .env
# --------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set in the environment. Aborting.")

# --------------------------------------------------
# 1) Utility: write data to CSV
# --------------------------------------------------
def writeToCSV(data, attributes, filename):
    if isinstance(data, dict):
        data = [data]
    if not attributes:
        attrs = set()
        for row in data:
            attrs.update(row.keys())
        attributes = sorted(attrs)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    exists = os.path.exists(filename)
    empty = not exists or os.path.getsize(filename) == 0
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=attributes)
        if empty:
            writer.writeheader()
        for row in data:
            writer.writerow({k: row.get(k, "") for k in attributes})

# --------------------------------------------------
# 2) Fuzzy matching helper
# --------------------------------------------------
def find_most_relevant_option(val, options):
    if val is None:
        return ""
    v = str(val).lower()
    best, score = "", 0.0
    for opt in options:
        s = difflib.SequenceMatcher(None, v, str(opt).lower()).ratio()
        if s > score:
            score, best = s, opt
    return best

# --------------------------------------------------
# 3) ChatGPT extraction prompt
# --------------------------------------------------
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
        {
            "role": "user",
            "content": f"Extract vehicle information from this text: {text}"
        }
    ]

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        raw = resp.choices[0].message.content
        print("RAW GPT→JSON (first 200 chars):", raw[:200].replace("\n", " "), "…")
        data = json.loads(raw)
        return data
    except Exception as e:
        print("Warning: failed to parse vehicle‐info JSON:", e)
        return None

# --------------------------------------------------
# 4) Normalize extracted info
# --------------------------------------------------
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
            return 1

        if constraint == "OS - Number of Fuel Tanks":
            return ""

        if constraint == "OS - Number of Rear Axles":
            return v  # override later based on config

        if constraint == "OS - Sleeper or Day Cab":
            return find_most_relevant_option(v, ["Day Cab", "Sleeper Cab"])

        if constraint == "OS - Transmission Make":
            opts = ["Aisin", "Allison", "Detroit", "Eaton Fuller", "Ford", "GM", "Mack",
                    "Mercedes-Benz", "Mitsubishi", "PACCAR", "Rockwell", "Spicer", "Volvo"]
            return find_most_relevant_option(v, opts)

        if constraint == "OS - Transmission Speeds":
            if v.isdigit():
                return f"{v}-speed"
            return find_most_relevant_option(v, [
                "2-speed","3-speed","4-speed","5-speed","6-speed",
                "7-speed","8-speed","9-speed","10-speed","12-speed",
                "13-speed","15-speed","18-speed"
            ])

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

        return v

    compliant = {}
    for field, constraint in field_constraints.items():
        compliant[field] = convert_value(extracted_info.get(field, ""), constraint)

    # Derive rear axles
    cfg = compliant.get("OS - Axle Configuration", "")
    if cfg in ("4 x 2", "4 x 4"):
        compliant["OS - Number of Rear Axles"] = 1
    elif cfg in ("6 x 2", "6 x 4", "6 x 6"):
        compliant["OS - Number of Rear Axles"] = 2
    elif cfg in ("8 x 4", "8 x 6"):
        compliant["OS - Number of Rear Axles"] = 3
    elif cfg == "10 x 4":
        compliant["OS - Number of Rear Axles"] = 4

    # Sync suspensions
    fst = compliant.get("OS - Front Suspension Type", "")
    rst = compliant.get("OS - Rear Suspension Type", "")
    if fst and not rst:
        compliant["OS - Rear Suspension Type"] = fst
    if rst and not fst:
        compliant["OS - Front Suspension Type"] = rst

    # Default Not Active
    if compliant.get("Not Active", "") == "":
        compliant["Not Active"] = 1

    # Clear unique id
    compliant["Unique id"] = ""

    return compliant

# --------------------------------------------------
# 5) Diagram info completion

def complete_diagram_info(diagram_info, compliant_info):
    """
    Given a partly‐filled diagram_info (with "Listing") and the compliant_info dict,
    return a dict with all required "Fx" and "Rx" fields initialized.
    """
    config = compliant_info.get("OS - Axle Configuration", "")
    fields = []
    if config in ("4 x 2", "4 x 4"):
        fields = ["F8","R1"]
    elif config in ("6 x 2", "6 x 4", "6 x 6"):
        fields = ["F8","R1","R2"]
    elif config in ("8 x 2", "8 x 4", "8 x 6", "8 x 8"):
        fields = ["F8","F7","R1","R2"]
    elif config == "10 x 4":
        fields = ["F8","F7","R1","R2","R3"]
    elif config == "10 x 6":
        fields = ["F8","F7","R1","R2","R3"]
    elif config == "10 x 8":
        fields = ["F8","F7","F6","R1","R2"]

    out = {"Listing": diagram_info["Listing"]}
    for f in fields:
        out[f+" Dual Tires"]    = ""
        out[f+" Lift Axle"]     = ""
        out[f+" Power Axle"]    = ""
        out[f+" Steer Axle"]    = ""
        out[f+" Tire Size"]     = ""
        out[f+" Wheel Material"]= ""

    # Default R1
    if "R1 Dual Tires" in out:
        out["R1 Dual Tires"] = "yes"
        out["R1 Lift Axle"]  = "no"
        out["R1 Power Axle"] = "yes"
        out["R1 Steer Axle"] = "no"

    return out





# --------------------------------------------------
# Selenium driver setup
# --------------------------------------------------
def get_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver

# --------------------------------------------------
# Get page text
# --------------------------------------------------
def get_vehicle_page_html(url):
    driver = get_driver()
    try:
        driver.get(url); time.sleep(5)
        if "Pardon Our Interruption" in driver.page_source:
            input("Solve CAPTCHA then Enter")
        WebDriverWait(driver,20).until(EC.presence_of_element_located((By.ID,"template")))
        soup=BeautifulSoup(driver.page_source,"html.parser")
        div=soup.find("div",id="template")
        return div.get_text(" ",strip=True) if div else ""
    except Exception as e:
        print("Page load error:", e)
        return ""
    finally:
        driver.quit()

# --------------------------------------------------
# Collect detail URLs
# --------------------------------------------------
def get_target_listings(category_url):
    base = "https://www.fydafreightliner.com"
    urls=[]
    driver=get_driver()
    try:
        driver.get(category_url); time.sleep(7)
        while True:
            driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
            time.sleep(5)
            WebDriverWait(driver,20).until(EC.presence_of_element_located((By.CSS_SELECTOR,"div.vehicle_row")))
            rows = BeautifulSoup(driver.page_source,"html.parser").select("div.vehicle_row")
            for r in rows:
                a=r.find("a",href=True)
                href=a["href"] if a else ""
                if href.startswith("/"): href=base+href
                urls.append(href)
            try:
                nxt=driver.find_element(By.ID,"next2")
                if nxt.get_attribute("disabled"): break
                nxt.click(); time.sleep(8)
            except:
                break
        return urls
    finally:
        driver.quit()

def get_listings():
    return get_target_listings("https://www.fydafreightliner.com/commercial-trucks-vans-for-sale-ky-oh-pa--xNewInventory#page=xNewInventory&vc=sleeper")

# --------------------------------------------------
# Download & watermark images
# --------------------------------------------------
def download_images_from_fyda(url, dest):
    driver = get_driver()
    os.makedirs(dest, exist_ok=True)
    urls = []

    try:
        # Load vehicle page
        driver.get(url)
        time.sleep(5)

        # Collect URLs from div.background-image
        for div in driver.find_elements(By.CSS_SELECTOR, "div.background-image"):
            s = div.get_attribute("style")
            m = re.search(r'url\((.*?)\)', s)
            if m:
                urls.append(m.group(1).strip('"\''))

        # Collect image src values from gallery and general <img> tags
        for img in driver.find_elements(By.CSS_SELECTOR, "div.galleryImages img") + driver.find_elements(By.TAG_NAME, "img"):
            src = img.get_attribute("src")
            if src and "inventory" in src:
                urls.append(src)

        # Remove duplicates
        urls = sorted(set(urls))
        print(f"Found {len(urls)} images for {url}")

        # Download all found image URLs
        paths = []
        for i, u in enumerate(urls, 1):
            ext = os.path.splitext(u.split("?", 1)[0])[1] or ".jpg"
            fname = os.path.join(dest, f"fyda_{i}{ext}")
            try:
                r = requests.get(u, timeout=10)
                r.raise_for_status()
                with open(fname, "wb") as f:
                    f.write(r.content)
                print(f"Downloaded {u} -> {fname}")
                paths.append(fname)
            except Exception as e:
                print(f"Failed to download {u}: {e}")

        return paths

    finally:
        driver.quit()


def watermark_images(files, outdir, wm):
    os.makedirs(outdir, exist_ok=True)

    for f in files:
        if not os.path.exists(f):
            print(f"Skipped missing file: {f}")
            continue

        output_path = os.path.join(outdir, os.path.basename(f))
        try:
            add_watermark(f, wm, output_path)
            print(f"Watermarked: {f} → {output_path}")
        except Exception as e:
            print(f"Watermark failed for {f}: {e}")


# --------------------------------------------------
# Run full scrape
# --------------------------------------------------
if __name__=="__main__":
    RESULTS="results"
    RAW=os.path.join(RESULTS,"images","fyda_raw")
    WM=os.path.join(RESULTS,"images","fyda")
    VEH=os.path.join(RESULTS,"vehicleinfo.csv")
    DIA=os.path.join(RESULTS,"diagram.csv")
    WATER="data/raw/group.png"
    for d in [RAW,WM,RESULTS]: os.makedirs(d,exist_ok=True)
    listings = get_listings()
    print(f"Running full scrape for {len(listings)} listings...")
    for url in listings:
        print(f"Processing: {url}")
        # extract + CSV
        text = get_vehicle_page_html(url)
        if not text: continue
        data = extract_vehicle_info(text)
        if not data: continue
        data.update({"Listing":url, "Original info description":text})
        comp = make_extracted_info_compliant(data)
        comp["original_image_url"]=url
        writeToCSV(comp, None, VEH)
        writeToCSV( complete_diagram_info({"Listing":url}, comp), None, DIA)
        # images
        imgs = download_images_from_fyda(url, RAW)
        if imgs:
            watermark_images(imgs, WM, WATER)
    print("Full scrape complete.")


# At the very bottom of scrapers/fyda_freightliner.py


def run(listing_url, veh_info_csv, diagram_csv, image_folder_root):
    """
    Orchestrates one FYDA listing:
     1) Fetch & parse
     2) Write CSV rows
     3) Download, rename & watermark images
    """
    print(f"[fyda] Processing → {listing_url}")

    # 1) Fetch page
    text = get_vehicle_page_html(listing_url)
    if not text:
        print(f"[fyda] No text for {listing_url}; skipping.")
        return

    # 2) Extract data
    data = extract_vehicle_info(text)
    if not data:
        print(f"[fyda] Extraction failed for {listing_url}; skipping.")
        return

    comp = make_extracted_info_compliant(data)
    comp["Listing"] = listing_url

    # 3) Write to CSVs
    writeToCSV(comp, None, veh_info_csv)
    writeToCSV(complete_diagram_info({"Listing": listing_url}, comp), None, diagram_csv)

    # 4) Download images
    raw_dir = os.path.join(image_folder_root, "fyda_raw")
    paths = download_images_from_fyda(listing_url, raw_dir)
    if paths:
        stock_no = str(comp.get("Stock Number", "unknown"))
        dest_dir = os.path.join(image_folder_root, stock_no)
        os.makedirs(dest_dir, exist_ok=True)

        for idx, src_path in enumerate(paths, start=1):
            ext = os.path.splitext(src_path)[1]
            dest_path = os.path.join(dest_dir, f"{idx}{ext}")
            os.replace(src_path, dest_path)
            print(f"Downloaded image {idx} → {dest_path}")
        print(f"Downloaded {len(paths)} images to {dest_dir}")

        # 5) Watermark
        wm_dir = os.path.join(image_folder_root, f"{stock_no}-watermarked")
        os.makedirs(wm_dir, exist_ok=True)
        for img_file in sorted(os.listdir(dest_dir)):
            src = os.path.join(dest_dir, img_file)
            out = os.path.join(wm_dir, img_file)
            add_watermark(src, "data/raw/group.png", out)
            print(f"Processed watermark for: {img_file}")

    # separator
    print("-" * 60)