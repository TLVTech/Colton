# scrapers/shanes_equipment.py
#  having issue with Pardon Our Interruption reCaptcha

import os
import re
import json
import csv
import time
import difflib
import random
import requests

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
import undetected_chromedriver as uc


#
# ── 0) Initialize OpenAI client from .env
#
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not found in environment.")


# original
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

# original
def extract_json(text):
    json_match = re.search(r'({.*})', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None

# original
def writeToCSV(data, attributes, filename):
    if isinstance(data, dict):
        data = [data]

    if not attributes:
        attributes = set()
        for item in data:
            attributes.update(item.keys())
        attributes = sorted(list(attributes))

    try:
        # Ensure the results directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        file_exists = os.path.exists(filename)
        file_empty = not file_exists or os.path.getsize(filename) == 0

        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=attributes)
            if file_empty:
                writer.writeheader()
            for item in data:
                row = {attr: item.get(attr, "") for attr in attributes}
                writer.writerow(row)

        print(f"Successfully wrote data to {filename}")
    except Exception as e:
        print(f"Error writing to CSV {filename}: {str(e)}")

# original
def extract_vehicle_info(text):
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
         The value of "OS - Vehicle Make" is case sensitive and the value must be one of the following: "Caterpillar", "Ford", "Freightliner", "GMC", "Hino", "International", "Kenworth", "Mack", "Peterbilt", "Sterling", "Volvo", "Western Star"
         """},
        {"role": "user", "content": f"Extract vehicle information from this text: {text}"}
    ]

    try:
        # Updated OpenAI API call for v1.0.0+
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        extracted_info = response.choices[0].message.content
        try:
            extracted_info = json.loads(extracted_info)
            return extracted_info
        except json.JSONDecodeError:
            print("Warning: Response was not valid JSON")
            return None
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return None

# original
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
        "Original info description": "text",
        "Origin": "text",
        "OS - Vehicle Make": "OS - Vehicle Make"
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
            val = get_closest_match(value, options)
            # Convert value to string before checking
            if str(value).lower() == '10':
                val = "10-speed"
            if str(value).lower() == '12':
                val = "12-speed"
            if str(value).lower() == '13':
                val = "13-speed"
            if str(value).lower() == '15':
                val = "15-speed"
            if str(value).lower() == '18':
                val = "18-speed"
            if str(value).lower() == '2':
                val = "2-speed"
            if str(value).lower() == '3':
                val = "3-speed"
            if str(value).lower() == '4':
                val = "4-speed"
            if str(value).lower() == '5':
                val = "5-speed"
            if str(value).lower() == '6':
                val = "6-speed"
            if str(value).lower() == '7':
                val = "7-speed"
            if str(value).lower() == '8':
                val = "8-speed"
            if str(value).lower() == '9':
                val = "9-speed"
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
        elif constraint == "OS - Vehicle Make":
            options = ["Caterpillar", "Ford", "Freightliner", "GMC", "Hino", "International", "Kenworth", "Mack", "Peterbilt", "Sterling", "Volvo", "Western Star"]
            val = get_closest_match(value, options)
            return val

        return value
    
    compliant_info = {}

    # Convert each field according to its constraint
    for field, constraint in field_constraints.items():
        original_value = extracted_info.get(field)
        compliant_info[field] = convert_value(original_value, constraint)

    return compliant_info

# original
def complete_diagram_info(diagram_info, compliant_info):
    # Try to determine axle configuration from available data
    config = compliant_info.get('OS - Axle Configuration', '')
    if not config:
        # Try to determine from number of axles
        num_front = compliant_info.get('OS - Number of Front Axles', '')
        num_rear = compliant_info.get('OS - Number of Rear Axles', '')
        
        if num_front == '1' and num_rear == '1':
            config = '4 x 2'
        elif num_front == '1' and num_rear == '2':
            config = '6 x 4'
        else:
            # Default to most common configuration if we can't determine
            config = '6 x 4'
            print(f"Using default axle configuration {config}")
    
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
        {"role": "user", "content": f"Extract vehicle information from this text: {mytext}"}
    ]
    
    try:
        # Use the new OpenAI client format
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=mymessages,
            temperature=0.1,
            max_tokens=1000
        )

        extracted_info = response.choices[0].message.content
        print("API Response:", extracted_info)  # Debug print
        
        try:
            extracted_info = json.loads(extracted_info)
            # Ensure no null values in the dictionary
            extracted_info = {k: '' if v is None else v for k, v in extracted_info.items()}
            # Merge with existing diagram info
            extracted_info.update(diagram_info)
            return extracted_info
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Raw response: {extracted_info}")
            return diagram_info  # Return basic diagram info even if extraction fails
            
    except Exception as e:
        print(f"Error during diagram info extraction: {str(e)}")
        return diagram_info  # Return basic diagram info even if API call fails

    return diagram_info

# original
# def get_driver(use_proxy=False, proxy=None):
#     options = webdriver.ChromeOptions()
#     options.add_argument('--no-sandbox')
#     options.add_argument('--disable-dev-shm-usage')
#     options.add_argument('--disable-gpu')
#     options.add_argument('--window-size=1920,1080')
    
#     # Add more convincing user agents
#     user_agents = [
#         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#         'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
#         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Edge/120.0.0.0',
#         'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
#     ]
#     options.add_argument(f'user-agent={random.choice(user_agents)}')
    
#     # Add common browser features to appear more human-like
#     options.add_argument('--enable-javascript')
#     options.add_argument('--accept-lang=en-US,en;q=0.9')
    
#     # Enable cookies
#     options.add_argument('--enable-cookies')
    
#     # Add random viewport size
#     viewports = [
#         (1920, 1080),
#         (1366, 768),
#         (1536, 864),
#         (1440, 900)
#     ]
#     viewport = random.choice(viewports)
#     options.add_argument(f'--window-size={viewport[0]},{viewport[1]}')

#     # Add proxy if specified
#     if use_proxy and proxy:
#         options.add_argument(f'--proxy-server={proxy}')

#     try:
#         # Use webdriver manager to automatically handle driver versions
#         from selenium.webdriver.chrome.service import Service
#         from webdriver_manager.chrome import ChromeDriverManager
        
#         service = Service(ChromeDriverManager().install())
#         driver = webdriver.Chrome(service=service, options=options)
#         # Set page load timeout
#         driver.set_page_load_timeout(30)
#         return driver
#     except WebDriverException as e:
#         print(f"ChromeDriver error: {str(e)}")
#         raise

# ❌ This version uses undetected-chromedriver + BrightData proxy
# ❌ Cloudflare closes the browser window immediately# import undetected_chromedriver as uc
# import random
# def get_driver():
#     opts = uc.ChromeOptions()
    
#     # Patch: Add dummy 'headless' attribute to prevent crashing
#     setattr(opts, "headless", False)

#     # Safe browser flags
#     opts.add_argument("--no-sandbox")
#     opts.add_argument("--disable-dev-shm-usage")
#     opts.add_argument("--disable-gpu")

#     # Viewport
#     viewports = [(1920, 1080), (1366, 768), (1440, 900), (1536, 864)]
#     vp = random.choice(viewports)
#     opts.add_argument(f"--window-size={vp[0]},{vp[1]}")

#     # User agent
#     uas = [
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.54 Safari/537.36",
#         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
#     ]
#     opts.add_argument(f"user-agent={random.choice(uas)}")

#     # Additional browser realism
#     opts.add_argument("--accept-lang=en-US,en;q=0.9")
#     opts.add_argument("--enable-javascript")
#     opts.add_argument("--enable-cookies")

#     # BrightData proxy injection
#     proxy = "brd-customer-hl_7e560da0-zone-residential_proxy_1:z0lycmag2k0c@brd.superproxy.io:33335"
#     opts.add_argument(f"--proxy-server=http://{proxy}")

#     print("[driver] Launching browser with BrightData proxy and undetected-chromedriver...")
#     driver = uc.Chrome(options=opts)
#     driver.set_page_load_timeout(30)
#     return driver











# original
def write_failed_url(url):
    with open('failed.txt', 'a') as f:
        f.write(url + '\n')

# original
# def get_vehicle_page_html(url):
#     driver = None
#     try:
#         driver = get_driver()
#         print("Loading vehicle page:", url)
        
#         # Add random delay before loading page (2-5 seconds)
#         time.sleep(random.uniform(2, 5))
#         driver.get(url)

#         # Add random scroll behavior
#         def human_like_scroll():
#             total_height = driver.execute_script("return document.body.scrollHeight")
#             current_height = 0
#             scroll_step = random.randint(100, 300)
            
#             while current_height < total_height:
#                 next_height = min(current_height + scroll_step, total_height)
#                 driver.execute_script(f"window.scrollTo({current_height}, {next_height})")
#                 current_height = next_height
#                 time.sleep(random.uniform(0.1, 0.3))  # Random delay between scrolls
                
#         # Random initial wait (8-12 seconds)
#         time.sleep(random.uniform(8, 12))
        
#         # Perform human-like scrolling
#         human_like_scroll()

#         time.sleep(2)
#         soup = BeautifulSoup(driver.page_source, 'html.parser')
#         detail_wrapper = soup.find('div', class_='detail-wrapper')
#         if detail_wrapper:
#             return detail_wrapper.get_text(strip=True, separator=' ')
#         else:
#             print("No detail-wrapper found in HTML.")
#             return ""
#     except Exception as e:
#         print(f"Error processing URL {url}: {str(e)}")
#         return ""
#     finally:
#         if driver:
#             driver.quit()

# ❌ This version uses undetected-chromedriver + BrightData proxy
# ❌ Cloudflare closes the browser window immediately
# def get_vehicle_page_html(url):
#     driver = None
#     try:
#         driver = get_driver()
#         print(f"[🔍] Loading vehicle page: {url}")

#         # Optional delay before navigation (to mimic natural behavior)
#         time.sleep(random.uniform(2, 5))

#         try:
#             driver.get(url)
#         except Exception as nav_err:
#             print(f"[❌] Failed to load URL: {url}")
#             print(f"    Navigation error: {str(nav_err)}")
#             return ""

#         # Simulate human-like scroll
#         def human_like_scroll():
#             try:
#                 total_height = driver.execute_script("return document.body.scrollHeight")
#                 current_height = 0
#                 scroll_step = random.randint(100, 300)

#                 while current_height < total_height:
#                     next_height = min(current_height + scroll_step, total_height)
#                     driver.execute_script(f"window.scrollTo({current_height}, {next_height})")
#                     current_height = next_height
#                     time.sleep(random.uniform(0.1, 0.3))
#             except Exception as scroll_err:
#                 print(f"[⚠️] Scroll error: {scroll_err}")

#         # Let the page settle before scroll
#         time.sleep(random.uniform(8, 12))
#         human_like_scroll()
#         time.sleep(2)

#         # Parse the final page HTML
#         soup = BeautifulSoup(driver.page_source, 'html.parser')
#         detail_wrapper = soup.find('div', class_='detail-wrapper')
#         if detail_wrapper:
#             return detail_wrapper.get_text(strip=True, separator=' ')
#         else:
#             print("[⚠️] No detail-wrapper found on page.")
#             return ""
#     except Exception as e:
#         print(f"[❌] Error processing vehicle URL {url}: {str(e)}")
#         return ""
#     finally:
#         if driver:
#             try:
#                 driver.quit()
#             except Exception as quit_err:
#                 print(f"[⚠️] Error while quitting driver: {quit_err}")


# # ✅ This version fetches vehicle detail page using BrightData Web Unlocker
# def get_vehicle_page_html(url):
#     try:
#         proxy_host = "brd.superproxy.io"
#         proxy_port = 22225
#         proxy_user = "brd-customer-hl_7e560da0-zone-aresi"
#         proxy_pass = "3el9pzsn1tl8"

#         proxies = {
#             "http": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
#             "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
#         }

#         headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
#             "Accept-Language": "en-US,en;q=0.9",
#         }

#         print(f"[🌐] Fetching detail page via Web Unlocker: {url}")
#         response = requests.get(url, headers=headers, proxies=proxies, timeout=30, verify=False)
#         with open("results/shane_debug.html", "w", encoding="utf-8") as f:
#             f.write(response.text)
#         response.raise_for_status()

#         soup = BeautifulSoup(response.text, 'html.parser')
#         detail_wrapper = soup.find('div', class_='detail-wrapper')
#         if detail_wrapper:
#             return detail_wrapper.get_text(strip=True, separator=' ')
#         else:
#             print("[⚠️] No detail-wrapper found.")
#             return ""

#     except Exception as e:
#         print(f"[❌] Error fetching vehicle page {url}: {e}")
#         return ""


# # ✅ Pulls vehicle detail page HTML via Web Unlocker API (direct API access)
# def get_vehicle_page_html(url):
    import requests
    import json
    from bs4 import BeautifulSoup

    api_key = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"

    print(f"[🌐] Fetching vehicle detail page via Web Unlocker API: {url}")
    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "zone": "aresi",
                "url": url,
                "method": "GET",
                "format": "raw"
            },
            timeout=30
        )
        response.raise_for_status()
        html = response.text

        with open("results/shane_debug_vehicle.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        detail_wrapper = soup.find('div', class_='detail-wrapper')
        if detail_wrapper:
            return detail_wrapper.get_text(strip=True, separator=' ')
        else:
            print("[⚠️] No detail-wrapper found.")
            return ""

    except Exception as e:
        print(f"[❌] Error fetching vehicle page {url}: {e}")
        return ""


# ✅ Fetches rendered vehicle page using BrightData Web Unlocker API
def get_vehicle_page_html(url):
    try:
        api_key = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"
        endpoint = "https://api.brightdata.com/unlocker/v1.0/portal"  # ✅ Correct endpoint

        payload = {
            "url": url,
            "render": True,  # 🧠 Ensures JS is executed server-side
            "country": "us",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        print(f"[🌐] Fetching vehicle detail page via Web Unlocker API (rendered): {url}")
        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()

        result = response.json()
        html = result.get("response", {}).get("body", "")

        if not html:
            print("[⚠️] No HTML found in response body.")
            return ""

        with open("results/shane_detail_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        detail_wrapper = soup.find('div', class_='detail-wrapper')
        if detail_wrapper:
            return detail_wrapper.get_text(strip=True, separator=' ')
        else:
            print("[⚠️] No detail-wrapper found in rendered HTML.")
            return ""

    except Exception as e:
        print(f"[❌] Error fetching vehicle page via Web Unlocker API: {e}")
        return ""








# original
# def get_target_listings():
#     url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"
#     inventory_prefix = "https://www.shanesequipment.com/inventory/"
#     all_urls = set()

#     driver = None
#     try:
#         driver = get_driver()
#         print(f"Navigating to URL: {url}")
        
#         # Add random delay before initial page load
#         time.sleep(random.uniform(3, 6))
#         driver.get(url)
        
#         # Random delay after page load
#         time.sleep(random.uniform(8, 12))

#         # Add random mouse movements (requires pyautogui)
#         def random_mouse_movement():
#             try:
#                 import pyautogui
#                 for _ in range(3):
#                     x = random.randint(100, 1000)
#                     y = random.randint(100, 600)
#                     pyautogui.moveTo(x, y, duration=random.uniform(0.5, 1.5))
#                     time.sleep(random.uniform(0.5, 1.5))
#             except ImportError:
#                 pass  # Skip if pyautogui not installed

#         random_mouse_movement()

#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(5)

#         if "Pardon Our Interruption" in driver.page_source:
#             print("Blocked by anti-bot on main page. Solve the CAPTCHA or try a proxy.")
#             input("Press Enter once you've solved any CAPTCHA in the browser...")
#             driver.refresh()
#             time.sleep(10)

#             if "Pardon Our Interruption" in driver.page_source:
#                 print("Still blocked. Cannot get listings.")
#                 return list(all_urls)

#         try:
#             WebDriverWait(driver, 30).until(
#                 EC.visibility_of_element_located((By.ID, "listContainer"))
#             )
#             print("listContainer found!")
#         except TimeoutException:
#             print("Could not find listContainer after a long wait.")
#             return list(all_urls)

#         while True:
#             time.sleep(3)
#             soup = BeautifulSoup(driver.page_source, 'html.parser')
#             list_container = soup.find('div', id='listContainer')
#             if list_container:
#                 links = list_container.find_all('a')
#                 for link in links:
#                     href = link.get('href')
#                     if href:
#                         if href.startswith('/'):
#                             href = "https://www.shanesequipment.com" + href
#                         if href.startswith(inventory_prefix):
#                             all_urls.add(href)

#                 try:
#                     next_button = WebDriverWait(driver, 5).until(
#                         EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Next Page']"))
#                     )
#                     if 'Mui-disabled' in next_button.get_attribute('class'):
#                         print("Next button disabled, no more pages.")
#                         break
#                     next_button.click()
#                     time.sleep(5)
#                 except:
#                     print("No next button, probably last page.")
#                     break
#             else:
#                 print("No listContainer found after initial success.")
#                 break
#     except WebDriverException as e:
#         print(f"WebDriver error: {str(e)}")
#     except Exception as e:
#         print(f"General error: {str(e)}")
#     finally:
#         if driver:
#             driver.quit()

#     return list(all_urls)


# # ✅ This version fetches Shane's inventory listings via BrightData Web Unlocker
# def get_target_listings():
#     try:
#         proxy_host = "brd.superproxy.io"
#         proxy_port = 22225
#         proxy_user = "brd-customer-hl_7e560da0-zone-aresi"
#         proxy_pass = "3el9pzsn1tl8"

#         proxies = {
#             "http": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
#             "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
#         }

#         headers = {
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
#             "Accept-Language": "en-US,en;q=0.9",
#         }

#         url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"
#         print(f"[🌐] Fetching listings page via Web Unlocker: {url}")
#         response = requests.get(url, headers=headers, proxies=proxies, timeout=30, verify=False)
#         with open("results/shane_debug.html", "w", encoding="utf-8") as f:
#             f.write(response.text)
#         response.raise_for_status()

#         soup = BeautifulSoup(response.text, "html.parser")
#         listings = soup.find_all("div", class_="listings-container")

#         urls = []
#         for div in listings:
#             a_tags = div.find_all("a", href=True)
#             for a in a_tags:
#                 href = a["href"]
#                 if href.startswith("/inventory/"):
#                     full_url = f"https://www.shanesequipment.com{href}"
#                     urls.append(full_url)

#         print(f"[✅] Found {len(urls)} vehicle URLs.")
#         return urls

#     except Exception as e:
#         print(f"[❌] Failed to get target listings: {e}")
#         return []

# # ✅ Pulls listings page HTML via BrightData Web Unlocker API (direct API access)
# def get_target_listings():
#     import requests
#     import json
#     from bs4 import BeautifulSoup
#     import os

#     api_key = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"
#     url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"

#     print(f"[🌐] Fetching listings page via Web Unlocker API: {url}")

#     try:
#         response = requests.post(
#             "https://api.brightdata.com/request",
#             headers={
#                 "Content-Type": "application/json",
#                 "Authorization": f"Bearer {api_key}"
#             },
#             json={
#                 "zone": "aresi",
#                 "url": url,
#                 "method": "GET",
#                 "format": "raw"
#             },
#             timeout=30
#         )
#         response.raise_for_status()
#         html = response.text

#         # Debug output
#         with open("results/shane_debug.html", "w", encoding="utf-8") as f:
#             f.write(html)

#         soup = BeautifulSoup(html, "html.parser")
#         container = soup.find("div", {"id": "listContainer"})
#         if not container:
#             print("[⚠️] listContainer not found.")
#             return []

#         urls = []
#         for a in container.find_all("a", href=True):
#             href = a["href"]
#             if href.startswith("/inventory/"):
#                 full_url = f"https://www.shanesequipment.com{href}"
#                 urls.append(full_url)

#         print(f"[✅] Found {len(urls)} vehicle URLs.")
#         return urls

#     except Exception as e:
#         print(f"[❌] Failed to get target listings: {e}")
#         return []

# # ✅ Fully render Shane's page using BrightData Web Unlocker with `render: true`
# def get_target_listings():
#     API_KEY = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"
#     ZONE = "aresi"
#     url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"

#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "zone": ZONE,
#         "url": url,
#         "render": True
#     }

#     print(f"[🌐] Fetching listings page via Web Unlocker API (rendered): {url}")
#     try:
#         response = requests.post("https://api.brightdata.com/web-unlock/request", headers=headers, json=payload, timeout=90)
#         response.raise_for_status()
#         html = response.json().get("response", {}).get("body", "")

#         with open("results/shane_debug_rendered.html", "w", encoding="utf-8") as f:
#             f.write(html)

#         soup = BeautifulSoup(html, "html.parser")
#         list_container = soup.find("div", id="listContainer")

#         urls = []
#         if list_container:
#             links = list_container.find_all("a", href=True)
#             for link in links:
#                 href = link["href"]
#                 if href.startswith("/inventory/"):
#                     urls.append(f"https://www.shanesequipment.com{href}")
#         else:
#             print("[⚠️] listContainer not found.")

#         print(f"[✅] Found {len(urls)} vehicle URLs.")
#         return urls

#     except Exception as e:
#         print(f"[❌] Failed to fetch rendered listings: {e}")
#         return []

# ✅ Use BrightData Web Unlocker with `render: true` (correct flow)
# def get_target_listings():
#     API_KEY = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"
#     ZONE = "aresi"
#     TARGET_URL = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"

#     trigger_url = "https://api.brightdata.com/dca/trigger"
#     fetch_url_base = "https://api.brightdata.com/dca/fetch"

#     headers = {
#         "Authorization": f"Bearer {API_KEY}",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "collector": "browser",  # ← key value for JS-rendered pages
#         "zone": ZONE,
#         "args": {
#             "url": TARGET_URL,
#             "render": True
#         }
#     }

#     print(f"[🌐] Triggering render job: {TARGET_URL}")
#     try:
#         # Step 1: Trigger
#         trigger_response = requests.post(trigger_url, headers=headers, json=payload)
#         trigger_response.raise_for_status()
#         job_id = trigger_response.json().get("job_id")
#         if not job_id:
#             print("[❌] Failed to get job ID.")
#             return []

#         # Step 2: Poll for result
#         for _ in range(20):  # wait max ~60 sec
#             time.sleep(3)
#             fetch_response = requests.get(f"{fetch_url_base}?job_id={job_id}", headers=headers)
#             if fetch_response.status_code == 200:
#                 break
#         else:
#             print("[❌] Timed out waiting for render job.")
#             return []

#         html = fetch_response.text
#         with open("results/shane_debug_rendered.html", "w", encoding="utf-8") as f:
#             f.write(html)

#         # Step 3: Parse vehicle links
#         soup = BeautifulSoup(html, "html.parser")
#         list_container = soup.find("div", id="listContainer")

#         urls = []
#         if list_container:
#             links = list_container.find_all("a", href=True)
#             for link in links:
#                 href = link["href"]
#                 if href.startswith("/inventory/"):
#                     urls.append(f"https://www.shanesequipment.com{href}")
#         else:
#             print("[⚠️] listContainer not found in rendered page.")

#         print(f"[✅] Found {len(urls)} vehicle URLs.")
#         return urls

#     except Exception as e:
#         print(f"[❌] Failed during Web Unlocker render flow: {e}")
#         return []


# ✅ Uses Web Unlocker API to fetch rendered search results page
def get_target_listings():
    try:
        api_key = "24b5c8102efcbc27e93429e9f18ba9a8bef51251357b3c1ae93773f303138b60"
        endpoint = "https://api.brightdata.com/unlocker/v1.0/portal"

        url = "https://www.shanesequipment.com/inventory/?/listings/search?ScopeCategoryIDs=27&Category=16013%7C16045&AccountCRMID=8589249&dlr=1&settingscrmid=5114963&lo=2"
        payload = {
            "url": url,
            "render": True,
            "country": "us",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        print(f"[🌐] Fetching listings page via Web Unlocker API: {url}")
        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()

        result = response.json()
        html = result.get("response", {}).get("body", "")

        if not html:
            print("[⚠️] Empty HTML received.")
            return []

        # Optional: write debug HTML to file
        with open("results/shane_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, "html.parser")
        list_container = soup.find("div", {"id": "listContainer"})

        urls = []
        if list_container:
            a_tags = list_container.find_all("a", href=True)
            for a in a_tags:
                href = a["href"]
                if href.startswith("/inventory/"):
                    full_url = f"https://www.shanesequipment.com{href}"
                    urls.append(full_url)
        else:
            print("[⚠️] listContainer not found.")

        print(f"[✅] Found {len(urls)} vehicle URLs.")
        return urls

    except Exception as e:
        print(f"[❌] Failed to fetch rendered listings: {e}")
        return []













# original
def get_failed_listings():
    if not os.path.exists('failed.txt'):
        return []
    with open('failed.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

# original
def run(url, filename, filename2, imagefolder):
    try:
        vehicle_text = get_vehicle_page_html(url)
        if not vehicle_text:
            print(f"No text content retrieved for {url}")
            return

        extracted_info = extract_vehicle_info(vehicle_text)
        if not extracted_info:
            print(f"No information could be extracted for {url}")
            return

        if isinstance(extracted_info, dict):
            # Add URL to the extracted info
            extracted_info["Listing"] = url
            extracted_info["Original info description"] = vehicle_text

            compliant_info = make_extracted_info_compliant(extracted_info)

            # Print some debug info
            print(f"Writing data for {url}")
            print(f"Data to be written: {compliant_info}")

            # Write to first CSV
            writeToCSV(compliant_info, None, filename)

            # Handle diagram info
            diagram_info = {"Listing": url}
            diagram_info2 = complete_diagram_info(diagram_info, compliant_info)
            print('diagram_info2')
            print(diagram_info2)
            print('*****************')

            if diagram_info2:
                writeToCSV(diagram_info2, None, filename2)
            else:
                print(f"No diagram info generated for {url}")
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")

# original
def process_vehicle_data(vehicle_info_path, diagram_data_path, vehicle_info_org_path, mylistings):
    # Create single output directory
    output_dir = "myresults"
    os.makedirs(output_dir, exist_ok=True)

    # Define the output file paths
    output_paths = {
        "vehicle": f"{output_dir}/vehicle_info.csv",
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

# original
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

# original
def main():
    # Ensure results directory exists
    results_dir = 'results'
    os.makedirs(results_dir, exist_ok=True)

    # Define full paths for output files
    vehicle_info_file = os.path.join(results_dir, 'vehicleinfo.csv')
    diagram_file = os.path.join(results_dir, 'diagram.csv')
    images_dir = os.path.join(results_dir, 'images')

    # Create images directory
    os.makedirs(images_dir, exist_ok=True)

    # Check if we should process failed URLs or get new listings
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'failed':
        listings = get_failed_listings()
        print(f'Processing {len(listings)} failed listings')
    else:
        listings = get_target_listings()
        print(f'Processing {len(listings)} new listings')

    total_listings = len(listings)
    print(f'Processing {total_listings} listings')

    mylistings = []

    for n, listing in enumerate(listings, 1):
        print(f'\nProcessing listing {n}/{total_listings}')
        print(f'URL: {listing}')
        mylistings.append(listing)
        # Add random delay between processing listings (30-60 seconds)
        if n > 1:  # Skip delay for first item
            delay = random.uniform(30, 60)
            print(f"Waiting {delay:.1f} seconds before next request...")
            time.sleep(delay)
            
        run(listing, vehicle_info_file, diagram_file, images_dir)
        print('===================')
    
    process_vehicle_data("./results/vehicleinfo.csv",
                         "./results/diagram.csv",
                         "./vehicle_info_org.csv",
                         mylistings)

# original
if __name__ == "__main__":
    main()

"""
once the code ran you can retry the failed listings by running the code again with the argument "failed"
python scrape.py failed


CAPTCHA detected! Please follow these steps:
1. Look at the browser window that opened
2. Complete the CAPTCHA verification
3. Wait a few seconds after completing the CAPTCHA
4. Press Enter once you've solved the CAPTCHA...
Still blocked after CAPTCHA. Trying one more time...
Access blocked. Consider:
- Using a different IP address
- Adding delays between requests
- Using a proxy service
"""

# ── Expose a flat `get_listings()` so that run_scraper.py can call it
def get_listings():
    return get_target_listings()


