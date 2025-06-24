# Colton/scrapers/jasper_trucks.py

# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
# ── Imports ──────────────────────────────────────────────────────────────────────
import os
import csv
import json
import re
import difflib
import requests
import openai
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin
from core.output import write_to_csv
from core.image_utils import extract_image_urls_from_page, download_images, watermark_images

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance
from PIL.Image import Resampling
import io
import cairosvg


# ── Load API key from environment ───────────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Aborting.")

# ── Constants ───────────────────────────────────────────────────────────────────
WATERMARK_PATH = os.path.join('data', 'raw', 'group.png')


# original function
#  ── Image Watermarking ─────────────────────────────────────────────────────────
def add_watermark(image_path, watermark_path, output_path, scale_factor=0.4, padding=60, opacity=0.35):
    try:
        # Load the base image and convert to RGBA
        base_image = Image.open(image_path)
        if base_image.format == 'WEBP' and base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')
        elif base_image.mode != 'RGBA':
            base_image = base_image.convert('RGBA')

        # Handle watermark based on file type
        if watermark_path.lower().endswith('.svg'):
            svg_data = cairosvg.svg2png(url=watermark_path)
            watermark = Image.open(io.BytesIO(svg_data)).convert("RGBA")
        else:
            watermark = Image.open(watermark_path).convert("RGBA")

        # Resize watermark
        new_wm_width = int(base_image.width * scale_factor)
        new_wm_height = int(new_wm_width * watermark.height / watermark.width)
        watermark = watermark.resize((new_wm_width, new_wm_height), Resampling.LANCZOS)

        # Apply transparency to the watermark
        watermark_with_opacity = Image.new('RGBA', watermark.size, (0, 0, 0, 0))
        for x in range(watermark.width):
            for y in range(watermark.height):
                r, g, b, a = watermark.getpixel((x, y))
                # Multiply the alpha channel by the opacity factor
                watermark_with_opacity.putpixel((x, y), (r, g, b, int(a * opacity)))

        # Position watermark
        pos = (
            padding,
            base_image.height - watermark_with_opacity.height - padding
        )

        # Create new image for composition
        final_image = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
        final_image.paste(base_image, (0, 0))
        final_image.paste(watermark_with_opacity, pos, watermark_with_opacity)

        # Convert and save based on output format
        output_ext = os.path.splitext(output_path)[1].lower()
        if output_ext == '.webp':
            final_image.save(output_path, 'WEBP', lossless=True, quality=90)
        else:
            final_image = final_image.convert("RGB")
            final_image.save(output_path)

        return output_path
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")

# original function
#  ── Folder Processing ──────────────────────────────────────────────────────────
def process_folder_watermark(input_folder, output_folder, watermark_path, scale_factor=0.60, padding=70, opacity=0.35):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(supported_formats):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                add_watermark(input_path, watermark_path, output_path, scale_factor, padding, opacity)
                print(f"Processed: {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")


# original function
# ── JSON-Cleaning Helpers ───────────────────────────────────────────────────────
def clean_json_string(json_string):
    # Remove Markdown code block markers if present
    json_string = re.sub(r'^```json\s*|\s*```$', '', json_string.strip())

    # Remove any leading/trailing whitespace
    json_string = json_string.strip()

    try:
        # Parse and then re-serialize to ensure proper JSON format
        parsed_json = json.loads(json_string)
        return json.dumps(parsed_json, indent=2)
    except json.JSONDecodeError as e:
        return f"Error: Could not parse JSON: {str(e)}"

#  original function
# # ── JSON Extraction ─────────────────────────────────────────────────────────────
def extract_json(text):
    # Find text between first { and last }
    json_match = re.search(r'({.*})', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            # Parse the extracted text to verify it's valid JSON
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None

# original function
# ── Diagram-Filling Logic ────────────────────────────────────────────────────────
def complete_diagram_info(diagram_info, compliant_info):
    config = compliant_info['OS - Axle Configuration']
    diagram_info = {}
    fields = []
    if config == '10 x 4':
        fields = ['F8','F7','R1','R2']
    if config == '10 x 6':
        fields = ['F8', 'F7', 'R1','R2','R3']
    if config == '10 x 8':
        fields = ['F8','F7', 'F6', 'R1', 'R2']
    if config == '4 x 2':
        fields = ['F8', 'R1']
    if config == '4 x 4':
        fields = ['F8', 'R1']
    if config == '6 x 2':
        fields = ['F8', 'R1']
    if config == '6 x 4':
        fields = ['F8', 'R1', 'R2']
    if config == '6 x 6':
        fields = ['F8', 'R1', 'R2']
    if config == '8 x 2':
        fields = ['F8', 'F7', 'R1']
    if config == '8 x 4':
        fields = ['F8', 'F7', 'R1', 'R2']
    if config == '8 x 6':
        fields = ['F8', 'R1', 'R2', 'R3']
    if config == '8 x 8':
        fields = ['F8', 'F7', 'R1', 'R2']

    for field in fields:
        diagram_info[field+ ' Dual Tires'] = ''
        diagram_info[field+ ' Lift Axle'] = ''
        diagram_info[field+ ' Power Axle'] = ''
        diagram_info[field+ ' Steer Axle'] = ''

    myfields = ""
    diagram_info['R1 Dual Tires'] = 'yes'
    diagram_info['R1 Lift Axle'] = 'no'
    diagram_info['R1 Power Axle'] = 'yes'
    diagram_info['R1 Steer Axle'] = 'no'
    myfields += 'field name: "R1 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
    myfields += 'field name: "R1 Tire Size", meaning: "Tire Size"'+'. '
    myfields += 'field name: "R1 Wheel Materia", meaning: "Rear Wheel Type" either Steel or Aluminum'+'. '

    if 'R2 Dual Tires' in diagram_info:
        diagram_info['R2 Dual Tires'] = 'yes'
    if 'R2 Lift Axle' in diagram_info:
        diagram_info['R2 Lift Axle'] = 'no'
    if 'R2 Power Axle' in diagram_info:
        diagram_info['R2 Power Axle'] = 'yes'
    if 'R2 Steer Axle' in diagram_info:
        diagram_info['R2 Steer Axle'] = 'no'
        myfields += 'field name: "R2 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "R2 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "R2 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum'+'. '


    if 'R3 Dual Tires' in diagram_info:
        diagram_info['R3 Dual Tires'] = 'no'
    if 'R3 Lift Axle' in diagram_info:
        diagram_info['R3 Lift Axle'] = 'yes'
    if 'R3 Power Axle' in diagram_info:
        diagram_info['R3 Power Axle'] = 'no'
    if 'R3 Steer Axle' in diagram_info:
        diagram_info['R3 Steer Axle'] = 'no'
        myfields += 'field name: "R3 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "R3 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "R3 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum'+'. '

    if 'R4 Dual Tires' in diagram_info:
        diagram_info['R4 Dual Tires'] = 'no'
    if 'R4 Lift Axle' in diagram_info:
        diagram_info['R4 Lift Axle'] = 'yes'
    if 'R4 Power Axle' in diagram_info:
        diagram_info['R4 Power Axle'] = 'no'
    if 'R4 Steer Axle' in diagram_info:
        diagram_info['R4 Steer Axle'] = 'no'
        myfields += 'field name: "R2 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "R2 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "R2 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum'+'. '

    diagram_info['F8 Dual Tires'] = 'no'
    diagram_info['F8 Lift Axle'] = 'no'
    diagram_info['F8 Power Axle'] = 'no'
    diagram_info['F8 Steer Axle'] = 'yes'
    myfields += 'field name: "F8 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
    myfields += 'field name: "F8 Tire Size", meaning: "Tire Size"'+'. '
    myfields += 'field name: "F8 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum'+'. '

    if 'F7 Dual Tires' in diagram_info:
        diagram_info['F7 Dual Tires'] = 'no'
    if 'F7 Lift Axle' in diagram_info:
        diagram_info['F7 Lift Axle'] = 'no'
    if 'F7 Power Axle' in diagram_info:
        diagram_info['F7 Power Axle'] = 'no'
    if 'F7 Steer Axle' in diagram_info:
        diagram_info['F7 Steer Axle'] = 'yes'
        myfields += 'field name: "F7 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "F7 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "F7 Wheel Material", meaning: "Steer Wheel Type"  either Steel or Aluminum'+'. '


    if 'F6 Dual Tires' in diagram_info:
        diagram_info['F6 Dual Tires'] = 'no'
    if 'F6 Lift Axle' in diagram_info:
        diagram_info['F6 Lift Axle'] = 'no'
    if 'F6 Power Axle' in diagram_info:
        diagram_info['F6 Power Axle'] = 'no'
    if 'F6 Steer Axle' in diagram_info:
        diagram_info['F6 Steer Axle'] = 'yes'
        myfields += 'field name: "F6 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "F6 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "F6 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum'+'. '


    if 'F5 Dual Tires' in diagram_info:
        diagram_info['F5 Dual Tires'] = 'no'
    if 'F5 Lift Axle' in diagram_info:
        diagram_info['F5 Lift Axle'] = 'no'
    if 'F5 Power Axle' in diagram_info:
        diagram_info['F5 Power Axle'] = 'no'
    if 'F5 Steer Axle' in diagram_info:
        diagram_info['F5 Steer Axle'] = 'no'
        myfields += 'field name: "F5 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified"'+'. '
        myfields += 'field name: "F5 Tire Size", meaning: "Tire Size"'+'. '
        myfields += 'field name: "F5 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum'+'. '


    mytext = compliant_info['Original info description']
    mymessages = [
        {"role": "system", "content": f"You are a vehicle data extraction assistant. Extract information from the text and return it in a JSON format with these fields:{myfields}"},
        {"role": "user", "content": f"Extract vehicle information from this text: {mytext}"}]
    print("mymessages")
    print(mymessages)
    try:
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                messages=mymessages,
                                                temperature=0.1,
                                                max_tokens=1000)

        #extracted_info = extract_json(response.choices[0].message.content)
        extracted_info = response.choices[0].message.content
        print("GREGORITY's first debug")
        # Try to parse and re-serialize to ensure valid JSON format
        try:
            extracted_info = json.loads(extracted_info)
            extracted_info = {k: '' if v is None else v for k, v in extracted_info.items()}
            extracted_info.update(diagram_info)
            return extracted_info
        except json.JSONDecodeError:
            print("Warning: Response was not valid JSON")
            return None

    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return None
    print('I should not see this')


    return ''

# ── Fuzzy-Match Helper ────────────────────────────────────────────────────────────
# Function to find the most relevant option
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

# original function
# ── Step 1: Get all listing URLs from JasperTrucks ─────────────────────────────────
def get_target_listings():
    base_url = "https://www.jaspertrucks.com/inventory.aspx"
    initial_params1 = {
        "new": "",
        "subtype": "Non-Sleeper",
        "make": "",
        "model": "",
        "enginemake": "",
        "enginemodel": "",
        "lyear": "",
        "hyear": ""
    }


    initial_params2 = {
        "new": "",
        "subtype": "Sleeper",
        "make": "",
        "model": "",
        "enginemake": "",
        "enginemodel": "",
        "lyear": "",
        "hyear": ""
    }



    # Use a set to store unique listings
    all_listings = set()

    def fetch_page(url, params=None):
        response = requests.get(url, params=params)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def process_page(soup):
        page_listings = set()  # Use a set for page listings too
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if '/inventory/SpecSheet_res/' in href:
                full_url = urljoin('https://www.jaspertrucks.com', href)
                page_listings.add(full_url)  # Add to set instead of list
        return page_listings

    def get_next_page_url(soup):
        next_page = soup.find('a', class_='page-next')
        if next_page and next_page.get('href'):
            return next_page['href']
        return None

    # Start with the first page
    current_params = initial_params1
    page_num = 1

    while True:
        print(f"Fetching page {page_num}...")
        if page_num > 1:
            current_params['Page'] = page_num

        soup = fetch_page(base_url, current_params)
        page_listings = process_page(soup)

        # Track number of new listings added
        previous_count = len(all_listings)
        all_listings.update(page_listings)
        new_listings = len(all_listings) - previous_count

        print(f"PAERAM1 Found {len(page_listings)} listings on page {page_num}, {new_listings} new unique listings")

        # Check for next page
        next_page = get_next_page_url(soup)
        if not next_page:
            break

        page_num += 1

    current_params = initial_params2
    page_num = 1

    while True:
        print(f"Fetching page {page_num}...")
        if page_num > 1:
            current_params['Page'] = page_num

        soup = fetch_page(base_url, current_params)
        page_listings = process_page(soup)

        # Track number of new listings added
        previous_count = len(all_listings)
        all_listings.update(page_listings)
        new_listings = len(all_listings) - previous_count

        print(f"PAERAM2 Found {len(page_listings)} listings on page {page_num}, {new_listings} new unique listings")

        # Check for next page
        next_page = get_next_page_url(soup)
        if not next_page:
            break

        page_num += 1

    # Convert set to sorted list for consistent output
    final_listings = sorted(list(all_listings))

    # Print results
    print("\nAll unique listings:")
    for listing in final_listings:
        print(listing)
    print(f"\nTotal unique listings found: {len(final_listings)}")

    return final_listings

#  original function
# ── Step 2: Write generic CSV writer ──────────────────────────────────────────────
def writeToCSV(data, attributes, filename):
    # If data is a single dictionary, convert it to a list
    if isinstance(data, dict):
        data = [data]

    # If attributes is not provided or is empty, use all keys from the data
    if not attributes:
        # Get all unique keys from all dictionaries in data
        attributes = set()
        for item in data:
            attributes.update(item.keys())
        attributes = sorted(list(attributes))  # Convert to sorted list for consistent order

    # Check if file exists and is empty
    file_exists = os.path.exists(filename)
    file_empty = not file_exists or os.path.getsize(filename) == 0

    # Open the file in append mode
    with open(filename, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=attributes)

        # Write the header only if the file is new or empty
        if file_empty:
            writer.writeheader()

        # Write each data item as a row
        print('data')
        print(data)
        for item in data:
            print('item ', item)
            # Extract only the specified attributes
            row = {attr: item.get(attr, "") for attr in attributes}  # Use empty string as default
            print('row')
            print(row)
            writer.writerow(row)

#  original function
# ── Step 3: Fetch and parse one vehicle page ───────────────────────────────────────
def get_vehicle_page_html(url):
    print('url: ', url)
    myid = url.split('=')[-1]
    url = f'https://www.jaspertrucks.com/inventory/SpecSheet_res/print.aspx?ID={myid}'

    try:
        session = requests.Session()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',  # Remove br (Brotli) from accepted encodings
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'}

        # Make request with modified headers
        response = session.get(
            url,
            headers=headers,
            allow_redirects=True,
            timeout=30,
            verify=False
        )

        # Print status for debugging
        print(f"Status Code: {response.status_code}")
        print(f"Final URL: {response.url}")

        if response.status_code == 200:
            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract all text while preserving structure
            text_content = []
            for tag in soup.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th', 'li']):
                if tag.parent.name not in ['script', 'style']:
                    text = tag.get_text(strip=True)
                    if text:
                        text_content.append(text)

            return '\n'.join(text_content)
        else:
            print(f"Failed to fetch page. Status code: {response.status_code}")
            return None

    except requests.RequestException as e:
        print(f"Error fetching the webpage: {str(e)}")
        return None

#  original function
# ── Step 4: Use OpenAI to extract JSON info from raw text ─────────────────────────
def extract_vehicle_info(text):
    # Define the system message to set the context
    messages = [
{"role": "system", "content": """You are a vehicle data extraction assistant.
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
         The field "Stock Number" is referred in the text as "UNIT#".
If the value of "Truck Type" is "Non-Sleeper", select "Day Cab" for the field "OS - Sleeper or Day Cab" Otherwise, select "Sleeper Cab".
The field "OS - Vehicle Make" is referred to in the text as "MAKE".
The field "Vehicle model - new" is referred to in the text as "MODEL".
If the value of "Odometer" is greater than 100, select "Pre-Owned" for the field "OS - Vehicle Condition", Otherwise, select "New".
The field "OS - Vehicle Type"  should always be "Semi-tractor truck".
The field "OS - Vehicle Class" should always be "Class 8".
The field "VehicleVIN" is referred in the text as "Serial No".
The value of  "Ref Number" should always be empty.
Just below "Contact Us", there is a city and state listed. Use the two letter state abbreviation found after the comma to select the correct state for the two fields "U.S. State" and "U.S. State (text)". These two fields should always contain an identical value.
The field "Company Address" should be empty.
The field "ECM Miles" is referred in the text as "ECM Mileage".
The field "Engine Serial Number" is referred in the text as "Engine Serial" if there is no value for "Engine Serial" in the text it should be empty.
If the field "Engine Serial Number" is the same as the field "VehicleVIN" then the field "Engine Serial Number" should be empty.
The field "Fuel Capacity" should be empty.
In the text if the "Axle Configuration" value is "Single" then the field "OS - Axle Configuration" should be "4 x 2".
In the text if the "Axle Configuration" value is "Tandem" then the field "OS - Axle Configuration" should be "6 x 4".
In the text if the "Axle Configuration" value is "Single" then the field "OS - Number of Front Axles" should be 1.
In the text if the "Axle Configuration" value is "Tandem" then the field "OS - Number of Front Axles" should be 1.
In the text if the "Axle Configuration" value is "Tandem" then the field "OS - Number of Rear Axles" should be 2.
In the text if the "Axle Configuration" value is "Single" then the field "OS - Number of Rear Axles" should be 1.
In the text if the "Suspension Type" value is "Air Ride" then the field "OS - Front Suspension Type" should be "Air Ride" otherwise it should empty.
In the text if the "Suspension Type" value is "Air Ride" then the field "OS - Rear Suspension Type" should be "Air Ride" otherwise it should empty.
 If the value of "Suspension Type" is not "Air Ride" then the value of the fields "OS - Front Suspension Type" and "OS - Rear Suspension Type" should be  empty.
The field "Not Active" should be set to the numeric value 1.
The field "Unique id" should always be empty."""},
        {"role": "user", "content": f"Extract vehicle information from this text: {text}"}
    ]

    try:
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                messages=messages,
                                                temperature=0.1,
                                                max_tokens=1000)

        extracted_info = response.choices[0].message.content
        print("jeremy's first debug")
        print(extracted_info)
        # Try to parse and re-serialize to ensure valid JSON format
        extracted_info = clean_json_string(extracted_info)
        try:
            extracted_info = json.loads(extracted_info)
            return extracted_info
        except json.JSONDecodeError:
            print("Warning: Response was not valid JSON")
            return None

    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return None

#  original function
# ── Step 5: Post-process extracted info to enforce constraints ────────────────────
def make_extracted_info_compliant(extracted_info):
    OSOptionAndFeatures = [
        "72\" sleeper", "Adaptive cruise control", "Air Conditioning", "Aluminum Fuel Tanks",
        "Automatic wipers", "Auxiliary Fuel Tanks", "Auxiliary Power Unit", "Backup Sensor",
        "Ball Hitch", "Block Heater", "Blower Motor", "Bluetooth System", "Bunk Heater",
        "Cab Extension Kit", "Cabinets", "CB Radio", "CD Player", "CE Plate", "Chrome Bumper",
        "Chrome Exhaust", "Cruise Control", "Desk", "Detachable rain tray", "Differential Lock",
        "Double Bunk", "Double Framed", "Drive Wheel Covers", "Dual Exhaust", "Dual Fuel Tanks",
        "Dual High Back Seats", "Dual Wetline", "Enclosed Cab", "Engine Brake", "EPA year: 2010",
        "EPA year: 2017", "Exterior color: black", "Exterior color: blue", "Exterior color: burgandy",
        "Exterior color: green", "Exterior color: grey", "Exterior color: orange", "Exterior color: purple",
        "Exterior color: red", "Exterior color: silver", "Exterior color: white", "Exterior color: yellow",
        "Fifth Wheel", "Fog Lights", "Full fairings", "Half fairings", "Headache Rack",
        "Heated Mirrors", "Heater", "Insulation Kit", "Integrated antennas", "Intelligent High Beam",
        "Lane Departure Warning", "Leather seats", "LED Headlights", "Left hand drive",
        "Locking Differentials", "Multifunction Steering Wheel", "Navigation System", "Overdrive",
        "Overhead storage console", "Pintle Hitch", "Power Locks", "Power Mirrors", "Power Take-Off",
        "Power Windows", "Raised Roof Sleeper", "Rear View Camera", "Refrigerator", "Roof Fairing",
        "Side Fairings", "Single bed", "Single exhaust", "Sleeper size: 110\"", "Sleeper size: 42\"",
        "Sleeper size: 60\"", "Sleeper size: 70\"", "Sleeper size: 72\"", "Sleeper size: 76\"",
        "Sleeper size: 96\"", "Sleeper type: Condo", "Sleeper type: Flat top", "Sleeper type: Mid roof",
        "Smartphone Connectivity", "Sofa", "Steering wheel mounted controls", "Sun visor",
        "Telescoping Steering Wheel", "Tilt Steering Wheel", "Tinted Glass", "Two beds",
        "UltraLoft Sleeper", "Wet Kit", "Winch", "Sleeper size: 82"
    ]

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
        "Listing": "Listing",
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
        "OS - Vehicle Make Logo": "OS - Vehicle Make Logo",
        "OS - Vehicle Type": "OS - Vehicle Type",
        "OS - Vehicle Year": "OS - Vehicle Year",
        "Rear Axle Capacity": "number",
        "Rear Axle Ratio": "number",
        "Ref Number": "number",
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

    def get_closest_match(value, options):
        # Handle empty or None input
        if not value:
            return ""

        # Convert value to string for comparison
        value_str = str(value).lower()
        # Convert all options to strings for comparison
        options_str = [str(opt).lower() for opt in options]

        closest_match = difflib.get_close_matches(value_str, options_str, n=1, cutoff=0.6)
        if not closest_match:
            return ""

        # Find the original option (number or string) that matches the closest string match
        match_idx = options_str.index(closest_match[0])
        return options[match_idx]

    def convert_value(value, constraint):
        if value is None or value == "":
            return ""  # Changed from None to ""

        if constraint == "number":
            try:
                # Remove any non-numeric characters except decimal points
                cleaned_value = ''.join(c for c in str(value) if c.isdigit() or c == '.')
                return float(cleaned_value) if '.' in cleaned_value else int(cleaned_value)
            except (ValueError, TypeError):
                return ""  # Changed from None to ""

        elif constraint == "text":
            return str(value).strip()

        elif isinstance(constraint, list):
            # For fields with specific allowed values
            value = str(value).strip().lower()
            for allowed_value in constraint:
                if value == allowed_value.lower():
                    return allowed_value
            return ""  # Changed from None to ""

        elif constraint == "OS - yes/no":
            if value.lower() in ["yes", "no"]:
                return value.lower()
            else:
                return ""

        elif constraint == "OS - Axle Configuration":
            options = ["10 x 4","10 x 6","10 x 8","4 x 2","4 x 4","6 x 2","6 x 4","6 x 6","8 x 2","8 x 4","8 x 6","8 x 8"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Brake System Type":
            options = ["Air", "Hydraulic"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Engine Make":
            options = ["Caterpillar", "Chevrolet", "Chrysler", "Continental", "Cummins", "Detroit", "DMC", "Dodge", "Duramax", "Eaton", "Ford", "GMC", "Hercules", "Hino", "International", "Isuzu", "John Deere", "Mack", "Mercedes-Benz", "Mitsubishi", "Navistar", "Nissan", "Other", "PACCAR", "Powerstroke", "Renault", "Toyota", "Volvo", "White"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Vehicle Model":
            options = [
                "108SD", "114SD", "122SD", "20", "195", "262", "2674SF", "268", "280", "330",
                "335", "337", "338", "348", "351", "351ST", "352", "352M", "352ST", "357",
                "359", "359EXHD", "360", "362", "365", "367", "375", "377", "378", "379",
                "379EXHD", "379X", "382", "384", "385", "386", "387", "388", "389", "389K",
                "389 Pride & Class", "389X", "537", "548", "567", "579", "4000", "4370",
                "579EV", "587", "589", "900", "4700", "47X", "4800", "4864F", "4900",
                "4900EX", "4900FA", "4900FA Lowmax", "4900FXT", "4900XD", "4946", "4964-2",
                "4964EX", "4964F", "4964FF", "4964FX", "4964X", "4984EX", "49X", "5700",
                "5700XE", "57X", "5800", "5900", "5964SS", "6900XD", "7000", "8100", "8200",
                "8400", "9000", "9100", "9200", "9300", "9400", "9600", "9670", "9700",
                "9800", "9900", "A9500", "A9513", "A9522", "ACL64", "Acterra", "Anthem 42R",
                "Anthem 42T", "Anthem 62T", "Anthem 64R", "Anthem 64T", "Anthem 84T", "Argosy",
                "AT9500", "AT9513", "B61T", "B73", "B75", "B81", "B87", "Brigadier", "Brute",
                "Business Class M2 100", "Business Class M2 106", "Business Class M2 106 Plus",
                "Business Class M2 112", "C500", "Cargostar", "Cascadia 113", "Cascadia 113 Evolution",
                "Cascadia 116", "Cascadia 125", "Cascadia 125 Evolution", "Cascadia 126", "CD825",
                "Century 112", "Century 120", "CF8000", "CH600", "CH603", "CH612", "CH613",
                "CHN612", "CHN613", "CL613", "CL653", "CL700", "CL713", "CL733", "COF4070B",
                "COF9670", "Columbia 112", "Columbia 120", "Coronado 114", "Coronado 122",
                "Coronado 122 SD", "Coronado 132", "CT660", "CT660L", "CT660S", "CT680", "CT680L",
                "DM688S", "DM690S", "DM800", "Durastar 4300", "Durastar 4400", "F2000D", "F2010A",
                "F650", "F700", "F8000", "FE42", "FL112", "FL70", "FL80", "FLA86", "FLB112",
                "FLB90", "FLC112", "FLC115", "FLC120", "FLC64T", "FLD112", "FLD112SD", "FLD120",
                "FLD120 Classic", "FLD132 Classic XL", "FLD162", "General", "Granite 64BT",
                "Granite 64FR", "Granite 64FT", "Granite 84FR", "Granite CT713", "Granite CTP713",
                "Granite CV513", "Granite CV613", "Granite CV713", "Granite GU713", "Granite GU813",
                "HV", "HX", "Icon 900", "K100", "L7500", "L7501", "L8000", "L8500", "L8501",
                "L9000", "L9500", "L9501", "L9513", "L9522", "LA9000", "LN8000", "LN9000",
                "Loadstar", "Lonestar", "LT", "LT625", "LT8500", "LT9500", "LT9501", "LT9513",
                "LTA9000", "LTL", "LTL9000", "LTLA9000", "MB80", "ME6500", "MH613", "MH653",
                "MR688S", "MRU613", "MV", "Paystar 5000", "Paystar 5070", "Paystar 5600",
                "Paystar 5900", "PI64", "Pinnacle 42R", "Pinnacle 64T", "Pinnacle CHU600",
                "Pinnacle CHU612", "Pinnacle CHU613", "Pinnacle CHU613 Rawhide", "Pinnacle CXP612",
                "Pinnacle CXP613", "Pinnacle CXU602", "Pinnacle CXU603", "Pinnacle CXU612",
                "Pinnacle CXU613", "Pinnacle CXU614", "Prostar", "R600", "R686ST", "R688",
                "R688ST", "R690ST", "RB690S", "RD600", "RD685", "RD686", "RD688", "RD688S",
                "RD688SX", "RD690S", "RD800SX", "RDF402", "RH", "RL686LST", "S2500", "S2600",
                "SC8000", "SF2574", "ST9500", "Superliner RW613", "Superliner RW736", "T2000",
                "T270", "T300", "T370", "T380", "T400", "T440", "T470", "T480", "T600", "T660",
                "T680", "T680E", "T700", "T800", "T880", "T880S", "Titan TD713", "Topkick C4500",
                "Topkick C7500", "Topkick C8500", "Transtar 4070", "Transtar 4300", "Transtar 8000",
                "Transtar 8300", "Transtar 8500", "Transtar 8600", "VHD64BT200", "VHD64BT300",
                "VHD64F300", "VHD64FT200", "VHD64FT300", "VHD64FT430", "VHD84BT200", "VHD84FT200",
                "VHD84FT400", "VHD84FT430", "Vision CX612", "Vision CX613", "Vision CXN612",
                "Vision CXN613", "VM310", "VNL42670", "VNL42780", "VNL42860", "VNL42T300",
                "VNL42T400", "VNL42T420", "VNL42T430", "VNL42T630", "VNL42T660", "VNL42T670",
                "VNL42T730", "VNL42T740", "VNL42T780", "VNL62T300", "VNL62T400", "VNL62T430",
                "VNL62T630", "VNL62T670", "VNL62T760", "VNL62T780", "VNL64T300", "VNL64T300 ARI",
                "VNL64T400", "VNL64T420", "VNL64T430", "VNL64T610", "VNL64T630", "VNL64T660",
                "VNL64T670", "VNL64T730", "VNL64T740", "VNL64T760", "VNL64T770", "VNL64T780",
                "VNL64T860", "VNL82T400", "VNL84T300", "VNL84T400", "VNL84T430", "VNL84T630",
                "VNL84T740", "VNL84T760", "VNM42T200", "VNM42T430", "VNM62T200", "VNM62T630",
                "VNM64T200", "VNM64T420", "VNM64T630", "VNM64T670", "VNM84T200", "VNR42T300",
                "VNR42T400", "VNR42T640", "VNR62T300", "VNR62T640", "VNR64T300", "VNR64T400",
                "VNR64T640", "VNR64T660", "VNR84T300", "VNR84T400", "VNR84T640", "VNX64T740",
                "VNX84T300", "VT64T800", "VT64T880", "VT84T830", "W900", "W900A", "W900B",
                "W900L", "W925", "W990", "WB123084", "WCA64T", "WCM64", "WFT8664T", "WG42",
                "WG42T", "WG64T", "WIA42", "WIA64T", "Workstar 7400", "Workstar 7500",
                "Workstar 7600", "Xpeditor"
            ]
            val = find_most_relevant_option(value, options)
            return val

        elif constraint == "OS - State":
            state_mapping = {
                "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
                "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
                "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
                "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
                "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
                "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
                "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
                "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
                "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
                "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
                "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
            }

            # Clean and standardize input
            value = str(value).strip().upper()

            # If it's a valid abbreviation, return the full name
            if value in state_mapping:
                return state_mapping[value]

            # If it's not an abbreviation, try to match the full name
            options = list(state_mapping.values())
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Vehicle Make Logo":
            return value

        elif constraint == "OS - Sleeper or Day Cab":
            options = ["Day Cab", "Sleeper Cab"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Fifth Wheel Type":
            options = ["Fixed", "Sliding"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Front Suspension Type":
            options = ["Air Ride", "Spring"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Transmission Type":
            options = ["Automatic", "Manual"]
            val = get_closest_match(value, options)
            if val == "":
              val = "Automatic"
            return val

        elif constraint == "OS - Transmission Make":
            options = ["Aisin", "Allison", "Detroit", "Eaton Fuller", "Ford", "GM", "Mack",
                      "Mercedes-Benz", "Meritor", "Mitsubishi", "PACCAR", "Rockwell", "Spicer",
                      "Torqshift", "Volvo"]
            val = get_closest_match(value, options)
            if value.lower()=='eaton':
                val = "Eaton Fuller"
            return val

        elif constraint == "OS - Transmission Speeds":
            options = ["10-speed", "12-speed", "13-speed", "15-speed", "18-speed", "2-speed",
                      "3-speed", "4-speed", "5-speed", "6-speed", "7-speed", "8-speed", "9-speed"]
            #val = get_closest_match(value, options)
            val = ""
            print('GREG AND JEREMY DEBUG OF OS - Transmission Speeds')
            print('value ', value)
            print('val ', val)
            value = str(value)
            if value.lower()=='10' :
                val = "10-speed"
            if value.lower()=='12' :
                val = "12-speed"
            if value.lower()=='13' :
                val = "13-speed"
            if value.lower()=='15' :
                val = "15-speed"
            if value.lower()=='18' :
                val = "18-speed"
            if value.lower()=='2' :
                val = "2-speed"
            if value.lower()=='3' :
                val = "3-speed"
            if value.lower()=='4' :
                val = "4-speed"
            if value.lower()=='5' :
                val = "5-speed"
            if value.lower()=='6' :
                val = "6-speed"
            if value.lower()=='7' :
                val = "7-speed"
            if value.lower()=='8' :
                val = "8-speed"
            if value.lower()=='9' :
                val = "9-speed"
            print('final val ', val)
            print('GREG AND JEREMY DEBUG OF OS - Transmission Speeds')
            return val

        elif constraint == "OS - Vehicle Condition":
            options = ["New", "Pre-Owned", "Used"]
            val = get_closest_match(value, options)
            if val == "Used":
                val = "Pre-Owned"
            return val

        elif constraint == "OS - Vehicle Type":
            options = ["Semi-tractor truck", ""]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Vehicle Year":
            return value

        elif constraint == "OS - Vehicle Class":
            options = ["Class 1", "Class 2A", "Class 2B", "Class 3", "Class 4", "Class 5", "Class 6", "Class 7", "Class 8"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Fuel Type":
            options = ["Bi-Fuel CNG", "BioDiesel", "Diesel", "Electric", "Flex Fuel",
                      "Gasoline", "Hybrid Electric", "Natural Gas", "Propane"]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Number of Front Axles":
            options = [1, 2, 3, 4, 5,6,7,8]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Number of Fuel Tanks":
            options = [1, 2, 3, 4, 5,6]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Number of Rear Axles":
            options = [1, 2, 3, 4, 5, 6, 7]
            val = get_closest_match(value, options)
            return val

        elif constraint == "OS - Rear Suspension Type":
            options = ["Air Ride", "Spring"]
            val = get_closest_match(value, options)
            return val

        return value

    compliant_info = {}

    # Convert each field according to its constraint
    for field, constraint in field_constraints.items():
        original_value = extracted_info.get(field)
        compliant_info[field] = convert_value(original_value, constraint)

    return compliant_info

#  original function
#  ── Step 6: Download images from the vehicle page ────────────────────────────────
def download_images(url, folder_name):
    import os
    import requests
    from bs4 import BeautifulSoup
    import re

    os.makedirs(folder_name, exist_ok=True)

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the div with id="photos"
        photos_div = soup.find('div', id='photos')
        if not photos_div:
            print("No div with id='photos' found")
            return

        # Find all img tags and links that might contain images
        image_elements = photos_div.find_all(['img', 'a'])
        image_urls = []

        # Extract URLs that contain 'xl'
        for element in image_elements:
            if element.name == 'img' and element.get('src'):
                url = element['src']
                if 'xl' in url.lower():
                    image_urls.append(url)

            if element.name == 'a' and element.get('href'):
                href = element['href']
                # Check for JavaScript function calls containing URLs
                if 'javascript:' in href:
                    # Extract URL from JavaScript function using regex
                    matches = re.findall(r"'(https?://[^']+)'", href)
                    for match in matches:
                        if 'xl' in match.lower():
                            image_urls.append(match)
                elif 'xl' in href.lower():  # Direct URLs
                    image_urls.append(href)

        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(image_urls))

        # Download images
        for index, img_url in enumerate(image_urls, start=1):
            try:
                # Handle relative URLs
                if not img_url.startswith(('http://', 'https://')):
                    img_url = requests.compat.urljoin(url, img_url)

                # Download image
                img_response = requests.get(img_url)
                img_response.raise_for_status()

                # Determine file extension from content type or URL
                content_type = img_response.headers.get('content-type', '')
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'png' in content_type:
                    ext = 'png'
                else:
                    # Try to get extension from URL
                    ext = img_url.split('.')[-1].lower()
                    if ext not in ['jpg', 'jpeg', 'png']:
                        ext = 'jpg'  # Default to jpg

                # Save image
                file_path = os.path.join(folder_name, f"{index}.{ext}")
                with open(file_path, 'wb') as f:
                    f.write(img_response.content)
                print(f"Downloaded image {index} to {file_path}")

            except Exception as e:
                print(f"Error downloading image {index}: {str(e)}")

        print(f"Downloaded {len(image_urls)} images to {folder_name}")

    except Exception as e:
        print(f"Error accessing URL: {str(e)}")



#   original function
# ── Step 7: "run()" orchestrator ───────────────────────────────────────────────
def run(url, filename, filename2, imagefolder):
    vehicle_text = get_vehicle_page_html(url)
    print(vehicle_text)
    extracted_info = extract_vehicle_info(vehicle_text)

    # Ensure extracted_info is a dictionary before assigning
    if isinstance(extracted_info, dict):
        extracted_info["Original info description"] = vehicle_text
        print("\nExtracted Vehicle Information:")
        print("-----------------------------")
        print(json.dumps(extracted_info, indent=2))

        # Only proceed with compliance check and CSV writing if we have valid data
        compliant_info = make_extracted_info_compliant(extracted_info)
        print("\nCompliant Vehicle Information:")
        print("-----------------------------")
        print(json.dumps(compliant_info, indent=2))

        attributes = ["Company Address",
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
                      "original_image_url"]
        compliant_info["original_image_url"] = url
        writeToCSV(compliant_info, attributes, filename)
        print('AAAAAAAAAaaaaaaa')
        diagram_info = {}
        diagram_info["original_image_url"] = url
        attributes2 = ["Listing",
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
                       "original_image_url"]

        diagram_info2 = complete_diagram_info(diagram_info, compliant_info)
        print('diagram_info before writing2')
        print(diagram_info2)
        print("attribute2")
        print(attributes2)
        writeToCSV(diagram_info2, attributes2, filename2)
        path1 = imagefolder+'/'+compliant_info['Stock Number']
        os.makedirs(path1, exist_ok=True)
        download_images(url, path1)
        process_folder_watermark(path1, path1+'-watermarked', WATERMARK_PATH, scale_factor=0.4, padding=60)


    else:
        print("No valid information extracted")
        print("Skipping CSV writing due to extraction failure")





listings = get_target_listings()
print('I should be processing ', len(listings), ' listins')
mylistings = listings
n = 0
for listing in mylistings:
  n += 1
  print('I am processing ', listing)
  os.makedirs('results', exist_ok=True)
  imagefolder = 'results/images'
  run(listing, 'results/vehicleinfo.csv', 'results/diagram.csv', imagefolder)
  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')
  print('listing ', n, ' over ', len(mylistings))

  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')
  print('*********************************************************************')



# original function
#  ── Process vehicle data and compare with original data ───────────────────
def process_vehicle_data(vehicle_info_path, diagram_data_path, vehicle_info_org_path, mylistings):
    # Create single output directory
    output_dir = "myresults"
    os.makedirs(output_dir, exist_ok=True)

    # Define the output file paths
    output_paths = {
        "vehicle": f"{output_dir}/vehicleinfo.csv",
        "diagram": f"{output_dir}/diagram_data.csv"
    }

    # Load original vehicle info into a dictionary for quick lookup
    org_vehicle_info = {}

    # First pass: read files and determine categories
    vehicle_data = []
    diagram_data = []

    # Read the original vehicle info into a dictionary
    with open(vehicle_info_org_path, "r", newline="") as org_file:
        org_reader = csv.DictReader(org_file)
        for row in org_reader:
            # Store the Price value using Stock Number as the key
            org_vehicle_info[row["Stock Number"]] = row["Price"]

    # Process vehicle info and diagram data files
    with open(vehicle_info_path, "r", newline="") as vehicle_file, \
         open(diagram_data_path, "r", newline="") as diagram_file:

        vehicle_reader = csv.DictReader(vehicle_file)
        diagram_reader = csv.DictReader(diagram_file)

        # Get headers
        vehicle_headers = vehicle_reader.fieldnames
        diagram_headers = diagram_reader.fieldnames

        # Process each line of the input files
        for index, (vehicle_row, diagram_row) in enumerate(zip(vehicle_reader, diagram_reader)):
            stock_number = vehicle_row["Stock Number"]
            vehicle_price = vehicle_row["Vehicle Price"]

            # Add dealerURL from mylistings if index is valid
            dealer_url = mylistings[index] if index < len(mylistings) else ""

            # Default upload type
            upload_type = "new"

            # Check if stock number exists in original data
            if stock_number in org_vehicle_info:
                org_price = org_vehicle_info[stock_number]

                # Compare vehicle prices (Vehicle Price from new file with Price from org file)
                # Convert both prices to floats for numerical comparison
                try:
                    # Handle empty strings or None values
                    vehicle_price_float = float(vehicle_price) if vehicle_price and vehicle_price.strip() else 0
                    org_price_float = float(org_price) if org_price and org_price.strip() else 0

                    # Compare the float values (with a small tolerance for floating point errors)
                    if abs(vehicle_price_float - org_price_float) < 0.01:
                        # Prices match - it's a "present" record
                        print(f"Prices match for Stock Number: {stock_number}")
                        print('----- ', vehicle_price, ' ', org_price)
                        upload_type = "present"
                    else:
                        print(f"Prices don't match for Stock Number: {stock_number}")
                        print('----- ', vehicle_price, ' ', org_price)
                        # Prices don't match - it's an "update" record
                        upload_type = "update"
                except (ValueError, TypeError):
                    # If conversion to float fails, compare as strings
                    # This is a fallback in case the data is not numeric
                    if vehicle_price == org_price:
                        # Strings match exactly
                        print(f"Prices match (string comparison) for Stock Number: {stock_number}")
                        print('----- ', vehicle_price, ' ', org_price)
                        upload_type = "present"
                    else:
                        print(f"Prices don't match (string comparison) for Stock Number: {stock_number}")
                        print('----- ', vehicle_price, ' ', org_price)
                        upload_type = "update"
            else:
                # Stock number not found - it's a "new" record
                print(f"Stock Number not found in original data: {stock_number}")
                upload_type = "new"

            # Add the new columns to the vehicle data
            vehicle_row["dealerURL"] = dealer_url
            vehicle_row["dealerUploadType"] = upload_type

            # Add the vehicle row to our list
            vehicle_data.append(vehicle_row)

            # Add the corresponding diagram row and the new columns
            diagram_row["dealerURL"] = dealer_url
            diagram_row["dealerUploadType"] = upload_type
            diagram_data.append(diagram_row)

    # Process all data using pandas for reordering
    reorder_and_save_results(
        vehicle_data,
        diagram_data,
        output_paths["vehicle"],
        output_paths["diagram"]
    )

    print("Processing complete!")



#  original function
# ── Reorder columns and save results to CSV ────────────────────────────────
def reorder_and_save_results(vehicle_data, diagram_data, out_vinf, out_ddata):
    # Convert dictionaries to pandas DataFrames
    vehicle_df = pd.DataFrame(vehicle_data)
    diagram_df = pd.DataFrame(diagram_data)

    # Extract Listing and Stock Number from vehicle_info
    listings_and_stock = vehicle_df[['Listing', 'Stock Number']]

    # Define ordered columns for vehicle_info
    ordered_columns_vehicle = [
        'Listing',
        'Stock Number',
        'dealerURL',
        'dealerUploadType',
        'OS - Vehicle Condition',
        'OS - Sleeper or Day Cab',
        'OS - Vehicle Year',
        'Vehicle Year',
        'OS - Vehicle Make',
        'Vehicle model - new',
        'Vehicle Price',
        'Odometer Miles',
        'OS - Vehicle Type',
        'OS - Vehicle Class',
        'glider',
        'VehicleVIN',
        'Ref Number',
        'U.S. State',
        'U.S. State (text)',
        'Company Address',
        'ECM Miles',
        'OS - Engine Make',
        'Engine Model',
        'Engine Horsepower',
        'Engine Displacement',
        'Engine Hours',
        'Engine Torque',
        'Engine Serial Number',
        'OS - Fuel Type',
        'OS - Number of Fuel Tanks',
        'Fuel Capacity',
        'OS - Transmission Speeds',
        'OS - Transmission Type',
        'OS - Transmission Make',
        'Transmission Model',
        'OS - Axle Configuration',
        'OS - Number of Front Axles',
        'OS - Number of Rear Axles',
        'Front Axle Capacity',
        'Rear Axle Capacity',
        'Rear Axle Ratio',
        'Wheelbase',
        'OS - Front Suspension Type',
        'OS - Rear Suspension Type',
        'OS - Fifth Wheel Type',
        'OS - Brake System Type',
        'OS - Vehicle Make Logo',
        'Location',
        'Not Active',
        'Unique id',
        'Original info description',
         "dealerURL",
         "dealerUploadType"
    ]

    # Create a reordered vehicle DataFrame
    vehicle_df_reordered = pd.DataFrame()
    for col in ordered_columns_vehicle:
        if col in vehicle_df.columns:
            vehicle_df_reordered[col] = vehicle_df[col]
        else:
            vehicle_df_reordered[col] = None

    # Create a new DataFrame for diagram data starting with Listing and Stock Number
    new_diagram_df = pd.DataFrame()
    new_diagram_df['Stock Number'] = listings_and_stock['Stock Number']
    new_diagram_df['Listing'] = listings_and_stock['Listing']

    # Add the new columns
    new_diagram_df['dealerURL'] = vehicle_df['dealerURL']
    new_diagram_df['dealerUploadType'] = vehicle_df['dealerUploadType']

    # Define ordered columns for diagram data
    ordered_columns_diagram = [
        'Stock Number',
        'Listing',
        'dealerURL',
        'dealerUploadType',
        'R1 Brake Type',
        'R1 Dual Tires',
        'R1 Lift Axle',
        'R1 Power Axle',
        'R1 Steer Axle',
        'R1 Tire Size',
        'R1 Wheel Material',
        'R2 Brake Type',
        'R2 Dual Tires',
        'R2 Lift Axle',
        'R2 Power Axle',
        'R2 Steer Axle',
        'R2 Tire Size',
        'R2 Wheel Material',
        'R3 Brake Type',
        'R3 Dual Tires',
        'R3 Lift Axle',
        'R3 Power Axle',
        'R3 Steer Axle',
        'R3 Tire Size',
        'R3 Wheel Material',
        'R4 Brake Type',
        'R4 Dual Tires',
        'R4 Lift Axle',
        'R4 Power Axle',
        'R4 Steer Axle',
        'R4 Tire Size',
        'R4 Wheel Material',
        'F5 Brake Type',
        'F5 Dual Tires',
        'F5 Lift Axle',
        'F5 Power Axle',
        'F5 Steer Axle',
        'F5 Tire Size',
        'F5 Wheel Material',
        'F6 Brake Type',
        'F6 Dual Tires',
        'F6 Lift Axle',
        'F6 Power Axle',
        'F6 Steer Axle',
        'F6 Tire Size',
        'F6 Wheel Material',
        'F7 Brake Type',
        'F7 Dual Tires',
        'F7 Lift Axle',
        'F7 Power Axle',
        'F7 Steer Axle',
        'F7 Tire Size',
        'F7 Wheel Material',
        'F8 Brake Type',
        'F8 Dual Tires',
        'F8 Lift Axle',
        'F8 Power Axle',
        'F8 Steer Axle',
        'F8 Tire Size',
        'F8 Wheel Material',
         "dealerURL",
         "dealerUploadType"
    ]

    # Add all diagram columns from original file while preserving order
    for col in ordered_columns_diagram[4:]:  # Skip Stock Number, Listing, dealerURL, and dealerUploadType as we already added them
        if col in diagram_df.columns:
            new_diagram_df[col] = diagram_df[col]
        else:
            new_diagram_df[col] = None

    # Write to output files
    vehicle_df_reordered.to_csv(out_vinf, index=False)
    new_diagram_df.to_csv(out_ddata, index=False)

    print(f"Successfully wrote reordered data to {out_vinf}")
    print(f"Successfully wrote reordered data to {out_ddata}")

process_vehicle_data(
    "/content/results/vehicleinfo.csv",
    "/content/results/diagram.csv",
    "/content/vehicle_info_org.csv",
    mylistings)

