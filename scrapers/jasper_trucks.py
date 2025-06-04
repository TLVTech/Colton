# Colton/scrapers/jasper_trucks.py
# works fine !
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
# ── Imports ──────────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
import os
import json
import re
import difflib
import requests
from bs4 import BeautifulSoup
import csv
from urllib.parse import urljoin

import openai

# ── Load API key from environment ───────────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Aborting.")


# ── JSON-Cleaning Helpers ───────────────────────────────────────────────────────
def clean_json_string(json_string: str) -> str:
    """
    Remove Markdown code fences and re-serialize to canonical JSON.
    """
    json_string = re.sub(r'^```json\s*|\s*```$', '', json_string.strip())
    json_string = json_string.strip()
    try:
        parsed = json.loads(json_string)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        return f"Error: Could not parse JSON: {str(e)}"


def extract_json(text: str):
    """
    Extract the first {} substring from `text`, parse it, and return as Python dict.
    """
    match = re.search(r'({.*})', text, re.DOTALL)
    if not match:
        return None
    candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# ── Diagram-Filling Logic ────────────────────────────────────────────────────────
def complete_diagram_info(diagram_info: dict, compliant_info: dict) -> dict:
    """
    Based on OS - Axle Configuration in compliant_info, build fields for R1, R2, etc.
    """
    config = compliant_info.get("OS - Axle Configuration", "")
    diagram_info = {}
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
    # Initialize each field set to empty
    for fld in fields:
        for suffix in [" Dual Tires", " Lift Axle", " Power Axle", " Steer Axle"]:
            diagram_info[f"{fld}{suffix}"] = ""

    # Hard-code defaults for R1 as an example
    diagram_info["R1 Dual Tires"] = "yes"
    diagram_info["R1 Lift Axle"] = "no"
    diagram_info["R1 Power Axle"] = "yes"
    diagram_info["R1 Steer Axle"] = "no"

    # (Repeat similar assignments for R2, R3, R4, F8, F7, etc. as needed.)

    return diagram_info


# ── Fuzzy-Match Helper ────────────────────────────────────────────────────────────
def find_most_relevant_option(input_value, options):
    """
    Return the single best fuzzy match from `options` for `input_value`.
    """
    best_match = None
    highest_score = 0.0
    for option in options:
        score = difflib.SequenceMatcher(
            None, str(input_value).lower(), str(option).lower()
        ).ratio()
        if score > highest_score:
            highest_score = score
            best_match = option
    return best_match or ""


# ── Step 1: Get all listing URLs from JasperTrucks ─────────────────────────────────
def get_target_listings() -> list:
    """
    Crawl both "Day Cab" and "Sleeper" categories on Jasper, collect all unique SpecSheet_res links.
    """
    base_url = "https://www.jaspertrucks.com/inventory.aspx"
    initial_params1 = {
        "new": "",
        "subtype": "Non-Sleeper",
        "make": "",
        "model": "",
        "enginemake": "",
        "enginemodel": "",
        "lyear": "",
        "hyear": "",
    }
    initial_params2 = {
        "new": "",
        "subtype": "Sleeper",
        "make": "",
        "model": "",
        "enginemake": "",
        "enginemodel": "",
        "lyear": "",
        "hyear": "",
    }

    all_listings = set()

    def fetch_page(url, params=None):
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def process_page(soup):
        page_links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/inventory/SpecSheet_res/" in href:
                full_url = urljoin("https://www.jaspertrucks.com", href)
                page_links.add(full_url)
        return page_links

    def get_next_page_url(soup):
        next_btn = soup.find("a", class_="page-next")
        return next_btn["href"] if (next_btn and next_btn.get("href")) else None

    # Crawl "Non-Sleeper"
    page_num = 1
    curr_params = dict(initial_params1)  # copy
    while True:
        if page_num > 1:
            curr_params["Page"] = page_num
        soup = fetch_page(base_url, curr_params)
        page_listings = process_page(soup)
        prev_count = len(all_listings)
        all_listings.update(page_listings)
        new_count = len(all_listings) - prev_count
        print(f"PARAM1 Page {page_num}: found {len(page_listings)} links, {new_count} new.")
        nxt = get_next_page_url(soup)
        if not nxt:
            break
        page_num += 1

    # Crawl "Sleeper"
    page_num = 1
    curr_params = dict(initial_params2)
    while True:
        if page_num > 1:
            curr_params["Page"] = page_num
        soup = fetch_page(base_url, curr_params)
        page_listings = process_page(soup)
        prev_count = len(all_listings)
        all_listings.update(page_listings)
        new_count = len(all_listings) - prev_count
        print(f"PARAM2 Page {page_num}: found {len(page_listings)} links, {new_count} new.")
        nxt = get_next_page_url(soup)
        if not nxt:
            break
        page_num += 1

    final_list = sorted(all_listings)
    print(f"\nTotal unique listings: {len(final_list)}")
    return final_list


# ── Step 2: Write generic CSV writer ──────────────────────────────────────────────
def write_to_csv(data, attributes, filename):
    """
    Append a list of dicts (or single dict) to CSV `filename` using fieldnames=attributes.
    """
    if isinstance(data, dict):
        data = [data]

    # If no attributes provided, collect keys from all dicts
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
            out_row = {attr: row.get(attr, "") for attr in attributes}
            writer.writerow(out_row)


# ── Step 3: Fetch and parse one vehicle page ───────────────────────────────────────
def get_vehicle_page_html(url: str) -> str:
    """
    Given a Jasper listing URL (SpecSheet_res), fetch the "print.aspx?ID=" page and extract all text.
    """
    myid = url.split("=")[-1]
    full_url = f"https://www.jaspertrucks.com/inventory/SpecSheet_res/print.aspx?ID={myid}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        resp = requests.get(full_url, headers=headers, allow_redirects=True, timeout=30, verify=False)
        print(f"Status Code: {resp.status_code} | URL: {resp.url}")
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # Collect all visible text tags
        pieces = []
        for tag in soup.find_all(
            ["p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "li"]
        ):
            if tag.parent.name not in ["script", "style"]:
                txt = tag.get_text(strip=True)
                if txt:
                    pieces.append(txt)
        return "\n".join(pieces)
    except Exception as e:
        print(f"Fetch error: {e}")
        return ""


# ── Step 4: Use OpenAI to extract JSON info from raw text ─────────────────────────
def extract_vehicle_info(text: str) -> dict:
    """
    Build a ChatCompletion prompt that asks GPT-3.5-turbo to extract the specified fields as JSON.
    This version first removes any “…” characters (U+2026) to avoid Latin-1 encoding errors,
    and wraps the OpenAI call in a try/except that prints repr(e) (ASCII-safe).
    """
    # 1) Clean out any literal “…” characters from the scraped text
    safe_text = text.replace("…", "...")

    # 2) Build the system and user messages exactly as before
    system_msg = {
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
Wheelbase. If a field is not found, leave it empty. Follow all special instructions as in the original spec.
"""
    }
    user_msg = {
        "role": "user",
        "content": f"Extract vehicle information from this text: {safe_text}"
    }

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[system_msg, user_msg],
            temperature=0.1,
            max_tokens=1000
        )
        extracted = resp.choices[0].message.content

        # Print the first 200 characters of GPT’s raw output for debugging
        print("RAW GPT→JSON (first 200 chars):", extracted[:200].replace("\n", " ") + " …")

        # Clean the JSON string (remove any ``` fences, pretty-print, etc.)
        extracted_clean = clean_json_string(extracted)

        try:
            return json.loads(extracted_clean)
        except json.JSONDecodeError:
            print("WARNING: Failed to parse JSON. Returning empty dict.")
            return {}
    except Exception as e:
        # Use repr(e) so that printing cannot trigger a UnicodeEncodeError
        print("OpenAI error:", repr(e))
        return {}



# ── Step 5: Post-process extracted info to enforce constraints ────────────────────
def make_extracted_info_compliant(extracted_info: dict) -> dict:
    """
    Given extracted_info (possibly from GPT), coerce each field to the expected type or allowed value.
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
        "Original info description": "text",
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
        elif constraint == "text":
            return val_str
        elif constraint == "OS - yes/no":
            val_low = val_str.lower()
            return val_low if val_low in ("yes", "no") else ""
        elif constraint == "OS - Axle Configuration":
            opts = [
                "10 x 4",
                "10 x 6",
                "10 x 8",
                "4 x 2",
                "4 x 4",
                "6 x 2",
                "6 x 4",
                "6 x 6",
                "8 x 2",
                "8 x 4",
                "8 x 6",
                "8 x 8",
            ]
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - Brake System Type":
            opts = ["Air", "Hydraulic"]
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - Engine Make":
            opts = [
                "Caterpillar",
                "Chevrolet",
                "Chrysler",
                "Continental",
                "Cummins",
                "Detroit",
                "DMC",
                "Dodge",
                "Duramax",
                "Eaton",
                "Ford",
                "GMC",
                "Hercules",
                "Hino",
                "International",
                "Isuzu",
                "John Deere",
                "Mack",
                "Mercedes-Benz",
                "Mitsubishi",
                "Navistar",
                "Nissan",
                "Other",
                "PACCAR",
                "Powerstroke",
                "Renault",
                "Toyota",
                "Volvo",
                "White",
            ]
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - Vehicle Model":
            opts = []
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - State":
            mapping = {
                "AL": "Alabama",
                "AK": "Alaska",
                "AZ": "Arizona",
                "AR": "Arkansas",
                "CA": "California",
                "CO": "Colorado",
                "CT": "Connecticut",
                "DE": "Delaware",
                "FL": "Florida",
                "GA": "Georgia",
                "HI": "Hawaii",
                "ID": "Idaho",
                "IL": "Illinois",
                "IN": "Indiana",
                "IA": "Iowa",
                "KS": "Kansas",
                "KY": "Kentucky",
                "LA": "Louisiana",
                "ME": "Maine",
                "MD": "Maryland",
                "MA": "Massachusetts",
                "MI": "Michigan",
                "MN": "Minnesota",
                "MS": "Mississippi",
                "MO": "Missouri",
                "MT": "Montana",
                "NE": "Nebraska",
                "NV": "Nevada",
                "NH": "New Hampshire",
                "NJ": "New Jersey",
                "NM": "New Mexico",
                "NY": "New York",
                "NC": "North Carolina",
                "ND": "North Dakota",
                "OH": "Ohio",
                "OK": "Oklahoma",
                "OR": "Oregon",
                "PA": "Pennsylvania",
                "RI": "Rhode Island",
                "SC": "South Carolina",
                "SD": "South Dakota",
                "TN": "Tennessee",
                "TX": "Texas",
                "UT": "Utah",
                "VT": "Vermont",
                "VA": "Virginia",
                "WA": "Washington",
                "WV": "West Virginia",
                "WI": "Wisconsin",
                "WY": "Wyoming",
            }
            up = val_str.upper()
            if up in mapping:
                return mapping[up]
            else:
                return find_most_relevant_option(val_str, list(mapping.values()))
        elif constraint == "OS - Sleeper or Day Cab":
            opts = ["Day Cab", "Sleeper Cab"]
            return find_most_relevant_option(val_str, opts)
        elif constraint in ("OS - Front Suspension Type", "OS - Rear Suspension Type"):
            opts = ["Air Ride", "Spring"]
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - Fuel Type":
            opts = [
                "Bi-Fuel CNG",
                "BioDiesel",
                "Diesel",
                "Electric",
                "Flex Fuel",
                "Gasoline",
                "Hybrid Electric",
                "Natural Gas",
                "Propane",
            ]
            return find_most_relevant_option(val_str, opts)
        elif constraint == "OS - Transmission Make":
            opts = [
                "Aisin",
                "Allison",
                "Detroit",
                "Eaton Fuller",
                "Ford",
                "GM",
                "Mack",
                "Mercedes-Benz",
                "Meritor",
                "Mitsubishi",
                "PACCAR",
                "Rockwell",
                "Spicer",
                "Torqshift",
                "Volvo",
            ]
            alt = find_most_relevant_option(val_str, opts)
            if val_str.lower() == "eaton":
                return "Eaton Fuller"
            return alt
        elif constraint == "OS - Transmission Speeds":
            if val_str.isdigit():
                return f"{val_str}-speed"
            return ""
        elif constraint == "OS - Transmission Type":
            opts = ["Automatic", "Manual"]
            alt = find_most_relevant_option(val_str, opts)
            return alt if alt else "Automatic"
        elif constraint == "OS - Vehicle Condition":
            opts = ["New", "Pre-Owned", "Used"]
            alt = find_most_relevant_option(val_str, opts)
            return "Pre-Owned" if alt == "Used" else alt
        elif constraint == "OS - Vehicle Type":
            return "Semi-tractor truck"
        elif constraint == "OS - Vehicle Class":
            return "Class 8"
        else:
            return val_str

    compliant = {}
    for field, constraint in field_constraints.items():
        val = extracted_info.get(field, "")
        compliant[field] = convert_value(val, constraint)
    return compliant


# ── Step 6: Image Download Logic ─────────────────────────────────────────────────
def download_images(url: str, folder_name: str) -> None:
    """
    Given the listing URL, parse <div id="photos"> for any "xl" images and save each as 1.jpg, 2.jpg, 
    """
    import os
    from bs4 import BeautifulSoup
    import requests
    import re

    os.makedirs(folder_name, exist_ok=True)
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        photos_div = soup.find("div", id="photos")
        if not photos_div:
            print("No photos div found.")
            return

        image_urls = []
        for el in photos_div.find_all(["img", "a"]):
            if el.name == "img" and el.get("src") and "xl" in el["src"].lower():
                image_urls.append(el["src"])
            if el.name == "a" and el.get("href"):
                href = el["href"]
                if "javascript:" in href:
                    matches = re.findall(r"'(https?://[^']+)'", href)
                    for m in matches:
                        if "xl" in m.lower():
                            image_urls.append(m)
                elif "xl" in href.lower():
                    image_urls.append(href)
        # remove duplicates, keep order
        unique_urls = list(dict.fromkeys(image_urls))
        for idx, img_url in enumerate(unique_urls, start=1):
            try:
                full_img_url = img_url if img_url.startswith(("http://", "https://")) else requests.compat.urljoin(url, img_url)
                img_resp = requests.get(full_img_url)
                img_resp.raise_for_status()
                content_type = img_resp.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                elif "png" in content_type:
                    ext = "png"
                else:
                    ext = img_url.split(".")[-1].lower()
                    if ext not in ("jpg", "jpeg", "png"):
                        ext = "jpg"
                file_path = os.path.join(folder_name, f"{idx}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(img_resp.content)
                print(f"Downloaded image {idx} → {file_path}")
            except Exception as e:
                print(f"Error downloading image {idx}: {e}")
        print(f"Downloaded {len(unique_urls)} images to {folder_name}")
    except Exception as e:
        print(f"Error accessing {url}: {e}")


# ── Step 7: "run()" orchestrator ───────────────────────────────────────────────
def run(
    listing_url: str,
    veh_info_csv: str,
    diagram_csv: str,
    image_folder_root: str,
) -> None:
    """
    1. Fetch raw text for `listing_url`
    2. Extract JSON with OpenAI → compliant_info
    3. Write vehicle CSV row and diagram CSV row
    4. Download images under image_folder_root/<Stock Number>/
    5. Watermark those images
    """
    vehicle_text = get_vehicle_page_html(listing_url)
    if not vehicle_text:
        print(f"Failed to fetch text for {listing_url}")
        return

    extracted = extract_vehicle_info(vehicle_text)
    if not isinstance(extracted, dict):
        print("Extraction failed.")
        return

    extracted["Original info description"] = vehicle_text
    compliant = make_extracted_info_compliant(extracted)

    # Set up output CSVs
    # Only make parent folders if they exist
    veh_dir = os.path.dirname(veh_info_csv)
    if veh_dir:
        os.makedirs(veh_dir, exist_ok=True)

    diag_dir = os.path.dirname(diagram_csv)
    if diag_dir:
        os.makedirs(diag_dir, exist_ok=True)

    # Write "vehicle" row
    vehicle_csv_fields = [
        "Company Address",
        "ECM Miles",
        "Engine Displacement",
        "Engine Horsepower",
        "Engine Hours",
        "Engine Model",
        "Engine Serial Number",
        "Engine Torque",
        "Front Axle Capacity",
        "Fuel Capacity",
        "glider",
        "Listing",
        "Location",
        "Not Active",
        "Odometer Miles",
        "OS - Axle Configuration",
        "OS - Brake System Type",
        "OS - Engine Make",
        "OS - Fifth Wheel Type",
        "OS - Front Suspension Type",
        "OS - Fuel Type",
        "OS - Number of Front Axles",
        "OS - Number of Fuel Tanks",
        "OS - Number of Rear Axles",
        "OS - Rear Suspension Type",
        "OS - Sleeper or Day Cab",
        "OS - Transmission Make",
        "OS - Transmission Speeds",
        "OS - Transmission Type",
        "OS - Vehicle Class",
        "OS - Vehicle Condition",
        "OS - Vehicle Make",
        "OS - Vehicle Make Logo",
        "OS - Vehicle Type",
        "OS - Vehicle Year",
        "Rear Axle Capacity",
        "Rear Axle Ratio",
        "Ref Number",
        "Stock Number",
        "Transmission Model",
        "U.S. State",
        "U.S. State (text)",
        "Vehicle model - new",
        "Vehicle Price",
        "Vehicle Year",
        "VehicleVIN",
        "Wheelbase",
        "Original info description",
        "original_image_url",
    ]
    compliant["original_image_url"] = listing_url
    write_to_csv(compliant, vehicle_csv_fields, veh_info_csv)

    # Write "diagram" row
    diagram_row = {"original_image_url": listing_url}
    diagram_fields = [
        "Listing",
        "R1 Brake Type",
        "R1 Dual Tires",
        "R1 Lift Axle",
        "R1 Power Axle",
        "R1 Steer Axle",
        "R1 Tire Size",
        "R1 Wheel Material",
        "R2 Brake Type",
        "R2 Dual Tires",
        "R2 Lift Axle",
        "R2 Power Axle",
        "R2 Steer Axle",
        "R2 Tire Size",
        "R2 Wheel Material",
        "R3 Brake Type",
        "R3 Dual Tires",
        "R3 Lift Axle",
        "R3 Power Axle",
        "R3 Steer Axle",
        "R3 Tire Size",
        "R3 Wheel Material",
        "R4 Brake Type",
        "R4 Dual Tires",
        "R4 Lift Axle",
        "R4 Power Axle",
        "R4 Steer Axle",
        "R4 Tire Size",
        "R4 Wheel Material",
        "F5 Brake Type",
        "F5 Dual Tires",
        "F5 Lift Axle",
        "F5 Power Axle",
        "F5 Steer Axle",
        "F5 Tire Size",
        "F5 Wheel Material",
        "F6 Brake Type",
        "F6 Dual Tires",
        "F6 Lift Axle",
        "F6 Power Axle",
        "F6 Steer Axle",
        "F6 Tire Size",
        "F6 Wheel Material",
        "F7 Brake Type",
        "F7 Dual Tires",
        "F7 Lift Axle",
        "F7 Power Axle",
        "F7 Steer Axle",
        "F7 Tire Size",
        "F7 Wheel Material",
        "F8 Brake Type",
        "F8 Dual Tires",
        "F8 Lift Axle",
        "F8 Power Axle",
        "F8 Steer Axle",
        "F8 Tire Size",
        "F8 Wheel Material",
        "original_image_url",
    ]
    diag_info = complete_diagram_info({}, compliant)
    # Ensure "Listing" exists
    diag_info["Listing"] = listing_url
    write_to_csv(diag_info, diagram_fields, diagram_csv)

    # Download images into e.g. "results/images/<Stock Number>/"
    stock = str(compliant.get("Stock Number", "")).strip()
    if stock:
        target_folder = os.path.join(image_folder_root, stock)
        download_images(listing_url, target_folder)
        # Watermark them
        watermark_path = os.path.join("data", "raw", "group.png")
        watermarked_folder = f"{target_folder}-watermarked"
        from core.watermark import process_folder_watermark

        process_folder_watermark(target_folder, watermarked_folder, watermark_path)
    else:
        print("No Stock Number; skipping images & watermark.")
