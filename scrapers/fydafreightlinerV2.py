# Full vehicle scraper pipeline with detailed comments

# === Standard and third-party imports ===
import os  # For file and directory handling
import re  # For regular expressions (not used yet, can be used for text parsing)
import json  # For working with JSON data
import csv  # For writing data to CSV files
import time  # For adding delays to mimic human behavior
import difflib  # For fuzzy matching strings
from bs4 import BeautifulSoup  # For parsing HTML
from openai import OpenAI  # OpenAI client to use GPT model
import random  # For selecting random user-agents
import requests  # For making HTTP requests (optional)

# Selenium and Chrome driver setup for browser automation
from selenium import webdriver  # For controlling the web browser
from selenium.webdriver.common.by import By  # For locating elements in the DOM
from selenium.webdriver.support.ui import WebDriverWait  # For waiting for elements to load
from selenium.webdriver.support import expected_conditions as EC  # For defining expected conditions for waits
from selenium.common.exceptions import TimeoutException, WebDriverException  # For handling exceptions during Selenium operations
from selenium.webdriver.chrome.service import Service  # For managing the ChromeDriver service
from webdriver_manager.chrome import ChromeDriverManager  # Automatically handles chromedriver setup

# === OpenAI Initialization ===
# Initialize OpenAI client (consider using environment variable for security)
client = OpenAI(api_key="your-openai-api-key")

# === Utility to get Selenium Chrome Driver ===
def get_driver(use_proxy=False, proxy=None):  
    """
    Launches a Chrome WebDriver with a random user-agent.
    Optionally supports proxies.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0)'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')  # Set a random user-agent

    if use_proxy and proxy:
        options.add_argument(f'--proxy-server={proxy}')  # Use proxy if enabled

    service = Service(ChromeDriverManager().install()) # Automatically install and manage ChromeDriver
    return webdriver.Chrome(service=service, options=options)  

# === Log failed URLs ===
def write_failed_url(url):  
    """
    Append failed URL to a text file for review or retry.
    """
    with open('failed.txt', 'a') as f:  
        f.write(url + '\n')  

# === Scrape all vehicle listing links from a dealer page ===
def get_target_listings(url):
    """
    Visits a dealer inventory page and extracts all vehicle listing URLs and text.
    Handles pagination dynamically.
    """
    base_url = "https://www.fydafreightliner.com"
    all_urls, all_texts = [], []
    driver = None

    try:
        driver = get_driver() # Initialize the Chrome driver
        print(f"Navigating to URL: {url}")  
        driver.get(url)  # Load the dealer inventory page
        time.sleep(10)  # Wait for page to fully load

        while True:  # Loop through pagination until no more pages
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # Scroll to the bottom of the page to load lazy-loaded content
            time.sleep(5)  # Scroll to load lazy-loaded content

            try:
                WebDriverWait(driver, 30).until(  # Wait for vehicle listings to load
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='vehicle_row']"))  
                )
                print("Vehicle listings found!")
            except TimeoutException:  # If no vehicle listings found, break the loop
                print("Could not find vehicle listings.")
                break  # Exit the loop if no listings found

            soup = BeautifulSoup(driver.page_source, 'html.parser')  # Parse the page source with BeautifulSoup
            vehicle_rows = soup.find_all('div', class_=lambda x: x and 'vehicle_row' in x)  # Find all vehicle rows

            for row in vehicle_rows:
                link = row.find('a')
                href = link.get('href') if link and link.get('href') else ""
                if href.startswith('/'):
                    href = base_url + href
                elif href and not href.startswith('http'):
                    href = base_url + '/' + href

                all_urls.append(href)
                all_texts.append(row.get_text(strip=True))
                print(f"Found vehicle listing: {href or 'No URL found'}")

            try:
                next_button = WebDriverWait(driver, 10).until(  # Wait for the next button to be clickable
                    EC.presence_of_element_located((By.ID, "next2"))  # ID of the next button
                )
                if next_button.get_attribute("disabled"):
                    print("Reached last page.")
                    break
                next_button.click()  # Click the next button to go to the next page
                time.sleep(10)
            except TimeoutException:  # If next button not found, break the loop
                print("Pagination finished or next button not found.")
                break

        return all_urls, all_texts  # Return all collected URLs and texts

    except WebDriverException as e:
        print(f"WebDriver error: {str(e)}")
        return [], []

    finally:
        if driver:  # Ensure the driver is closed properly
            driver.quit()

# === Extract full text description from vehicle page ===
def get_vehicle_page_html(url):
    """
    Opens the vehicle detail page and returns its description as text.
    """
    driver = None
    try:
        driver = get_driver()
        print("Loading vehicle page:", url)
        driver.get(url)  # Navigate to the vehicle detail page
        time.sleep(15)

        # CAPTCHA check
        if "Pardon Our Interruption" in driver.page_source:
            print("CAPTCHA detected. Please resolve manually.")
            input("Press Enter after CAPTCHA...")
            driver.refresh()  
            time.sleep(10)
            if "Pardon Our Interruption" in driver.page_source:
                write_failed_url(url)
                return ""

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # Scroll to the bottom to load all content
        time.sleep(5)

        WebDriverWait(driver, 20).until(  # Wait for the detail wrapper to load
            EC.presence_of_element_located((By.CLASS_NAME, "detail-wrapper"))  # This class contains the vehicle details
        )

        soup = BeautifulSoup(driver.page_source, 'html.parser')  
        wrapper = soup.find('div', class_='detail-wrapper')  # Find the main wrapper containing vehicle details
        return wrapper.get_text(strip=True, separator=' ') if wrapper else ""  

    except Exception as e:
        print(f"Error with URL {url}: {str(e)}")
        return ""

    finally:
        if driver:
            driver.quit()

# === Use GPT to extract structured info ===
def extract_vehicle_info(text):
    """
    Sends a description to OpenAI GPT to extract vehicle info in JSON format.
    """
    messages = [
        {"role": "system", "content": "Extract vehicle details from the given text and return JSON."},
        {"role": "user", "content": f"Extract vehicle information from this text: {text}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print("Error extracting info:", e)
        return None

# === Normalize GPT-extracted info ===
def make_extracted_info_compliant(info):
    """
    Cleans and standardizes extracted fields using simple rules and fuzzy matching.
    """
    def get_closest_match(value, options):
        if not value:
            return ""
        value = str(value).lower()  # Normalize input value to lowercase
        options_lower = [opt.lower() for opt in options]  
        match = difflib.get_close_matches(value, options_lower, n=1, cutoff=0.6)  # Fuzzy match with a cutoff
        return options[options_lower.index(match[0])] if match else ""  # Return the closest match if found, else return empty string

    def convert_value(val, type_):  # Convert values based on their type
        if val is None or val == "":
            return ""
        if type_ == "number":
            try:
                clean = ''.join(c for c in str(val) if c.isdigit() or c == '.')  # Remove non-numeric characters except for decimal points
                return float(clean) if '.' in clean else int(clean)  # Convert to float or int
            except:
                return ""
        elif type_ == "text":
            return str(val).strip()  # Strip whitespace from text
        elif type_ == "OS - Fuel Type":
            return get_closest_match(val, ["Diesel", "Electric", "Gasoline"])
        elif type_ == "OS - Axle Configuration":
            return get_closest_match(val, ["4 x 2", "6 x 4", "8 x 6"])
        return val

    constraints = {
        "Vehicle Year": "number",
        "OS - Fuel Type": "OS - Fuel Type",
        "OS - Axle Configuration": "OS - Axle Configuration",
        "VehicleVIN": "text"
    }

    return {field: convert_value(info.get(field), rule) for field, rule in constraints.items()}  # Normalize fields based on defined rules

# === Write cleaned data to CSV ===
def writeToCSV(data, attributes, filename):  
    """
    Appends structured data to a CSV file. Creates header row if file is empty.
    """
    if isinstance(data, dict):   #If a single dictionary is passed instead of a list of dictionaries, we wrap it in a list so the rest of the code can treat it the same way.
        data = [data]

    if not attributes: # If no attributes are provided, we extract them from the data
        attributes = set() # Initialize an empty set to collect unique attributes
        for item in data: # Iterate through each item in the data
            attributes.update(item.keys())  # Add the keys of each item to the set
        attributes = sorted(list(attributes)) # Convert the set back to a sorted list for consistent order

    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)  # Ensure the directory exists, create it if not
        file_exists = os.path.exists(filename)  # Check if the file already exists
        file_empty = not file_exists or os.path.getsize(filename) == 0  # Check if the file is empty

        with open(filename, mode='a', newline='', encoding='utf-8') as file:  # Open the file in append mode, create it if it doesn't exist
            writer = csv.DictWriter(file, fieldnames=attributes)  # Create a CSV writer with the specified attributes
            if file_empty: # If the file is empty, write the header row
                writer.writeheader()  # Write the header row only if the file is empty
            for item in data: # Iterate through each item in the data
                writer.writerow({attr: item.get(attr, "") for attr in attributes}) # Write each item as a row in the CSV, filling missing attributes with empty strings

        print(f"Saved to {filename}")  # Log successful write
    except Exception as e:  # Catch any exceptions during file operations
        print(f"Failed to write CSV: {e}")  # Log the error message
