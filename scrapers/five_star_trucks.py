# Colton/scrapers/five_star_trucks.py
# works fine!

import os
import re
import json
import csv
import time
import difflib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import openai
from core.output import write_to_csv

# ── Configuration ───────────────────────────────────────────────────────────────
# (Pull OPENAI_API_KEY from .env via dotenv if you wish, or rely on environment variable.)
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set. Aborting.")


# ── (A) 1) Get all listing URLs ────────────────────────────────────────────────
def get_listings() -> list:
    """
    Crawl https://www.5startrucksales.us/semi-trucks/ to collect individual-truck links.
    """
    base_url = "https://www.5startrucksales.us/semi-trucks/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(base_url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # All links of the form https://www.5startrucksales.us/trucks…
        truck_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("https://www.5startrucksales.us/trucks"):
                truck_links.append(href)

        return sorted(set(truck_links))
    except Exception as e:
        print(f"[get_listings] Error: {e}")
        return []


# ── (B) 2) Fetch raw page HTML / text ──────────────────────────────────────────
def get_vehicle_page_html(url: str) -> str:
    """
    Given a 5 Star Truck URL, GET/parse the page and return the visible text (everything up to “You may also like”).
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        full_text = soup.get_text(separator=" ", strip=True)

        marker = "You may also like"
        idx = full_text.find(marker)
        if idx != -1:
            return full_text[:idx].strip()
        return full_text
    except Exception as e:
        print(f"[get_vehicle_page_html] Error fetching {url}: {e}")
        return ""


# ── (C) 3) Use OpenAI to extract JSON info ─────────────────────────────────────
def extract_json_from_text(text: str) -> dict:
    """
    Search for the first { … } substring in `text`, parse to JSON, return dict or {}.
    """
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if not match:
        return {}
    candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


def extract_vehicle_info(text: str) -> dict:
    """
    Wraps OpenAI ChatCompletion. Prompts GPT‐3.5‐turbo to emit a JSON object
    with exactly the fields specified in the Colton spec.
    """
    # 1) Clean the text (avoid fancy ellipses)
    safe_text = text.replace("…", "...")

    system_msg = {
        "role": "system",
        "content": """
You are a vehicle data extraction assistant.
Extract information from this text and return it in JSON format with these fields:
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
Wheelbase. If a field is not found, leave it empty. Follow all special instructions in the original spec.
"""
    }
    user_msg = {"role": "user", "content": f"Extract vehicle information from this text: {safe_text}"}

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[system_msg, user_msg],
            temperature=0.1,
            max_tokens=1000
        )
        raw_output = resp.choices[0].message.content
        # Extract the JSON part
        return extract_json_from_text(raw_output)
    except Exception as e:
        print(f"[extract_vehicle_info] OpenAI error: {e}")
        return {}


# ── (D) 4) Coerce fields to “compliant” values ────────────────────────────────
def find_most_relevant_option(input_value, options):
    best, best_score = "", 0.0
    for opt in options:
        score = difflib.SequenceMatcher(None, str(input_value).lower(), str(opt).lower()).ratio()
        if score > best_score:
            best_score = score
            best = opt
    return best


def make_extracted_info_compliant(extracted_info: dict) -> dict:
    """
    Given the raw dict from GPT, coerce each field into the Colton constraints (numbers, text, dropdowns, etc.).
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
        "Original info description": "text",
    }

    def convert_value(val, constraint):
        if val is None or val == "":
            return ""
        text_val = str(val).strip()

        if constraint == "number":
            cleaned = "".join(c for c in text_val if c.isdigit() or c == ".")
            try:
                return int(cleaned) if "." not in cleaned else float(cleaned)
            except:
                return ""
        elif constraint == "text":
            return text_val
        elif constraint == "OS - yes/no":
            low = text_val.lower()
            return low if low in ("yes", "no") else ""
        elif constraint == "OS - Axle Configuration":
            opts = ["10 x 4","10 x 6","10 x 8","4 x 2","4 x 4","6 x 2","6 x 4","6 x 6","8 x 2","8 x 4","8 x 6","8 x 8"]
            return find_most_relevant_option(text_val, opts)
        elif constraint == "OS - Brake System Type":
            return find_most_relevant_option(text_val, ["Air", "Hydraulic"])
        elif constraint == "OS - Engine Make":
            eng_opts = ["Caterpillar","Chevrolet","Chrysler","Continental","Cummins","Detroit","Dodge","Ford","GMC","International","Isuzu","Mack","Mercedes-Benz","Navistar","Volvo","Other"]
            return find_most_relevant_option(text_val, eng_opts)
        elif constraint == "OS - Vehicle Model":
            # You can supply your full list of models here if desired
            return text_val
        elif constraint == "OS - State":
            mapping = {
                "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
                "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
                "ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas",
                "KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
                "MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana",
                "NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico",
                "NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma",
                "OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota",
                "TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
                "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"
            }
            up = text_val.upper()
            if up in mapping:
                return mapping[up]
            else:
                return find_most_relevant_option(text_val, list(mapping.values()))
        elif constraint == "OS - Sleeper or Day Cab":
            return find_most_relevant_option(text_val, ["Day Cab", "Sleeper Cab"])
        elif constraint in ("OS - Front Suspension Type", "OS - Rear Suspension Type"):
            return find_most_relevant_option(text_val, ["Air Ride", "Spring"])
        elif constraint == "OS - Fuel Type":
            return find_most_relevant_option(text_val, ["Diesel","Gasoline","Hybrid Electric","Electric","CNG","Propane"])
        elif constraint == "OS - Transmission Make":
            return find_most_relevant_option(text_val, ["Allison","Eaton Fuller","Meritor","Mack","Volvo","Other"])
        elif constraint == "OS - Transmission Speeds":
            if text_val.isdigit():
                return f"{text_val}-speed"
            return ""
        elif constraint == "OS - Transmission Type":
            return find_most_relevant_option(text_val, ["Automatic","Manual"]) or "Automatic"
        elif constraint == "OS - Vehicle Condition":
            cond = find_most_relevant_option(text_val, ["New","Pre-Owned","Used"])
            return "Pre-Owned" if cond == "Used" else cond
        elif constraint == "OS - Vehicle Type":
            return "Semi-tractor truck"
        elif constraint == "OS - Vehicle Class":
            return "Class 8"
        else:
            return text_val

    compliant = {}
    for fld, constr in field_constraints.items():
        compliant[fld] = convert_value(extracted_info.get(fld, ""), constr)
    return compliant


# ── (E) 5) Build diagram info ───────────────────────────────────────────────────
def complete_diagram_info(diagram_info: dict, compliant_info: dict) -> dict:
    """
    Mirror the logic from Jasper but adapted:
    Based on “OS - Axle Configuration” in compliant_info, populate R1, R2, F7, F8 fields.
    """
    config = compliant_info.get("OS - Axle Configuration", "")
    diagram_info = {}
    fields = []
    if config == "10 x 4":
        fields = ["F8","F7","R1","R2"]
    elif config == "10 x 6":
        fields = ["F8","F7","R1","R2","R3"]
    elif config == "10 x 8":
        fields = ["F8","F7","F6","R1","R2"]
    elif config in ("4 x 2","4 x 4","6 x 2"):
        fields = ["F8","R1"]
    elif config == "6 x 4":
        fields = ["F8","R1","R2"]
    elif config == "6 x 6":
        fields = ["F8","R1","R2"]
    elif config == "8 x 2":
        fields = ["F8","F7","R1"]
    elif config == "8 x 4":
        fields = ["F8","F7","R1","R2"]
    elif config == "8 x 6":
        fields = ["F8","R1","R2","R3"]
    elif config == "8 x 8":
        fields = ["F8","F7","R1","R2"]

    for fld in fields:
        for suffix in [" Dual Tires"," Lift Axle"," Power Axle"," Steer Axle"]:
            diagram_info[f"{fld}{suffix}"] = ""

    # Hard‐code R1 defaults as in Colton spec
    diagram_info["R1 Dual Tires"] = "yes"
    diagram_info["R1 Lift Axle"] = "no"
    diagram_info["R1 Power Axle"] = "yes"
    diagram_info["R1 Steer Axle"] = "no"
    #… add R2, R3, F7, F8 defaults exactly as you want …

    return diagram_info


# ── (F) 6) Download gallery images ───────────────────────────────────────────────
def download_gallery_images(url: str, folder_name: str) -> None:
    """
    Parse <a.e-gallery-item.elementor-gallery-item> nodes on each truck page,
    download each image, name them “1.jpg, 2.jpg, …” and save under folder_name.
    """
    os.makedirs(folder_name, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        gallery_links = soup.select("a.e-gallery-item.elementor-gallery-item")
        if not gallery_links:
            print("[download_gallery_images] No gallery links found.")
            return

        unique_urls = []
        for a in gallery_links:
            href = a.get("href") or ""
            if href.startswith("http"):
                unique_urls.append(href)
            else:
                # Maybe it’s “javascript:…’URL’” style
                matches = re.findall(r"'(https?://[^']+)'", href)
                for m in matches:
                    unique_urls.append(m)

        # De‐dupe while preserving order
        seen = set()
        final_urls = []
        for img_url in unique_urls:
            if img_url not in seen:
                seen.add(img_url)
                final_urls.append(img_url)

        for idx, img_url in enumerate(final_urls, start=1):
            try:
                resp_img = requests.get(img_url, headers=headers, timeout=30)
                resp_img.raise_for_status()
                ext = "jpg"
                ctype = resp_img.headers.get("content-type", "")
                if "png" in ctype:
                    ext = "png"
                file_path = os.path.join(folder_name, f"{idx}.{ext}")
                with open(file_path, "wb") as f:
                    f.write(resp_img.content)
                print(f"[download_gallery_images] Downloaded {file_path}")
            except Exception as e:
                print(f"[download_gallery_images] Error downloading {img_url}: {e}")
        print(f"[download_gallery_images] Done → {len(final_urls)} images")
    except Exception as e:
        print(f"[download_gallery_images] Error accessing {url}: {e}")




# ── (H) 8) run() orchestrator ───────────────────────────────────────────────────
def run(
    listing_url: str,
    veh_info_csv: str,
    diagram_csv: str,
    image_folder_root: str
) -> None:
    """
    1. get raw text
    2. extract via OpenAI → compliant_info
    3. write vehicle CSV & diagram CSV
    4. download images → watermarked folder
    """
    # 1) fetch text
    vehicle_text = get_vehicle_page_html(listing_url)
    if not vehicle_text:
        print(f"[run] Failed to fetch text for {listing_url}")
        return

    # 2) extract → compliant
    extracted = extract_vehicle_info(vehicle_text)
    if not isinstance(extracted, dict):
        print(f"[run] Extraction failed for {listing_url}")
        return

    extracted["Original info description"] = vehicle_text
    compliant = make_extracted_info_compliant(extracted)

    # 3a) write “vehicle” row
    veh_fields = [
        "Company Address","ECM Miles","Engine Displacement","Engine Horsepower","Engine Hours",
        "Engine Model","Engine Serial Number","Engine Torque","Front Axle Capacity","Fuel Capacity",
        "glider","Listing","Location","Not Active","Odometer Miles","OS - Axle Configuration",
        "OS - Brake System Type","OS - Engine Make","OS - Fifth Wheel Type","OS - Front Suspension Type",
        "OS - Fuel Type","OS - Number of Front Axles","OS - Number of Fuel Tanks","OS - Number of Rear Axles",
        "OS - Rear Suspension Type","OS - Sleeper or Day Cab","OS - Transmission Make",
        "OS - Transmission Speeds","OS - Transmission Type","OS - Vehicle Class","OS - Vehicle Condition",
        "OS - Vehicle Make","OS - Vehicle Make Logo","OS - Vehicle Type","OS - Vehicle Year",
        "Rear Axle Capacity","Rear Axle Ratio","Ref Number","Stock Number","Transmission Model",
        "U.S. State","U.S. State (text)","Vehicle model - new","Vehicle Price","Vehicle Year",
        "VehicleVIN","Wheelbase","Original info description","original_image_url"
    ]
    compliant["original_image_url"] = listing_url
    write_to_csv(compliant, veh_fields, veh_info_csv)

    # 3b) write “diagram” row
    diag_row = {"original_image_url": listing_url}
    diag_fields = [
        "Listing","R1 Brake Type","R1 Dual Tires","R1 Lift Axle","R1 Power Axle","R1 Steer Axle",
        "R1 Tire Size","R1 Wheel Material","R2 Brake Type","R2 Dual Tires","R2 Lift Axle",
        "R2 Power Axle","R2 Steer Axle","R2 Tire Size","R2 Wheel Material",
        "R3 Brake Type","R3 Dual Tires","R3 Lift Axle","R3 Power Axle","R3 Steer Axle","R3 Tire Size","R3 Wheel Material",
        "R4 Brake Type","R4 Dual Tires","R4 Lift Axle","R4 Power Axle","R4 Steer Axle","R4 Tire Size","R4 Wheel Material",
        "F5 Brake Type","F5 Dual Tires","F5 Lift Axle","F5 Power Axle","F5 Steer Axle","F5 Tire Size","F5 Wheel Material",
        "F6 Brake Type","F6 Dual Tires","F6 Lift Axle","F6 Power Axle","F6 Steer Axle","F6 Tire Size","F6 Wheel Material",
        "F7 Brake Type","F7 Dual Tires","F7 Lift Axle","F7 Power Axle","F7 Steer Axle","F7 Tire Size","F7 Wheel Material",
        "F8 Brake Type","F8 Dual Tires","F8 Lift Axle","F8 Power Axle","F8 Steer Axle","F8 Tire Size","F8 Wheel Material",
        "original_image_url"
    ]
    diag_info = complete_diagram_info({}, compliant)
    diag_info["Listing"] = listing_url
    write_to_csv(diag_info, diag_fields, diagram_csv)

    # 4) download images + watermark
    stock = str(compliant.get("Stock Number","")).strip()
    if stock:
        target_folder = os.path.join(image_folder_root, stock)
        download_gallery_images(listing_url, target_folder)
        watermark_path = os.path.join("data", "raw", "group.png")
        watermarked_folder = f"{target_folder}-watermarked"
        from core.watermark import process_folder_watermark
        process_folder_watermark(target_folder, watermarked_folder, watermark_path)
    else:
        print(f"[run] No Stock Number for {listing_url}; skipping images.")
