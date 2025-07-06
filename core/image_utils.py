# core/image_utils.py

import os
import re
from typing import List
import requests
import requests.compat
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def download_images(image_urls: List[str], dest_folder: str, dealer: str = None, prefix: str = "") -> List[str]:
    """
    Download a list of image URLs to dest_folder.
    Uses proxy only for ftlgr (imanpro) images.
    Returns list of file paths.
    """
    os.makedirs(dest_folder, exist_ok=True)
    saved_paths = []

    # Proxy config from environment (if needed)
    proxy_user = os.environ.get("BRIGHTDATA_PROXY_USER")
    proxy_pass = os.environ.get("BRIGHTDATA_PROXY_PASS")
    proxy_host = os.environ.get("BRIGHTDATA_PROXY_HOST")
    proxy_port = os.environ.get("BRIGHTDATA_PROXY_PORT")

    for idx, url in enumerate(image_urls, 1):
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        filename = os.path.join(dest_folder, f"{prefix}{idx}{ext}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/106.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }
        proxies = None
        session = requests.Session()
        # Only use proxy for FTLGR dealer (safe for all other scrapers)
        if dealer == "ftlgr":
            # For hotlink protection and proxy
            headers["Referer"] = "https://www.ftlgr.com/"
            proxies = {
                "http": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
                "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
            }
        try:
            resp = session.get(url, headers=headers, timeout=30, verify=False, proxies=proxies)
            resp.raise_for_status()
            with open(filename, "wb") as f:
                f.write(resp.content)
            saved_paths.append(filename)
            print(f"Downloaded image {idx} -> {filename}")
        except Exception as e:
            print(f"Error downloading {url}: {e}")

    print(f"Downloaded {len(saved_paths)} images to {dest_folder}")
    return saved_paths


def watermark_images(input_paths: List[str], output_folder: str, watermark_path: str) -> None:
    """
    Given a list of existing image file paths, apply the watermark (via core.watermark)
    and save into output_folder with the same filenames.
    """
    from core.watermark import add_watermark

    os.makedirs(output_folder, exist_ok=True)
    for img_path in input_paths:
        fname = os.path.basename(img_path)
        out_path = os.path.join(output_folder, fname)
        try:
            add_watermark(img_path, watermark_path, out_path)
            print(f"Processed watermark for: {fname}")
        except Exception as e:
            print(f"Failed watermark {fname}: {e}")


def extract_image_urls_from_page(listing_url: str, dealer: str = "jasper", container_id: str = "photos"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/106.0.0.0 Safari/537.36"
    }

    proxies = None
    # Use proxy only for ftlgr
    if dealer == "ftlgr":
        proxies = {
            "http": f"http://{os.environ['BRIGHTDATA_PROXY_USER']}:{os.environ['BRIGHTDATA_PROXY_PASS']}@{os.environ['BRIGHTDATA_PROXY_HOST']}:{os.environ['BRIGHTDATA_PROXY_PORT']}",
            "https": f"http://{os.environ['BRIGHTDATA_PROXY_USER']}:{os.environ['BRIGHTDATA_PROXY_PASS']}@{os.environ['BRIGHTDATA_PROXY_HOST']}:{os.environ['BRIGHTDATA_PROXY_PORT']}",
        }

    resp = requests.get(listing_url, headers=headers, timeout=15, verify=False, proxies=proxies)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []

    if dealer == "five_star":
        # 1. Anchor gallery (Elementor or similar)
        gallery_links = soup.select('a.e-gallery-item.elementor-gallery-item')
        if gallery_links:
            for a_tag in gallery_links:
                img_url = a_tag.get("href")
                if img_url and "/uploads/" in img_url:
                    urls.append(urljoin(listing_url, img_url))

        # 2. <img> tags inside the gallery block
        gallery_div = soup.find("div", class_="gallery")
        if gallery_div:
            for img in gallery_div.find_all("img"):
                img_url = img.get("src")
                if img_url and "/uploads/" in img_url:
                    urls.append(urljoin(listing_url, img_url))

        # 3. As fallback, ANY <img> with uploads in the URL
        if not urls:
            for img in soup.find_all("img"):
                img_url = img.get("src")
                if img_url and "/uploads/" in img_url:
                    urls.append(urljoin(listing_url, img_url))
        # Remove duplicates while keeping order
        urls = list(dict.fromkeys(urls))
        print("Extracted gallery URLs:", urls)
        return urls

    if dealer == "jasper":
        div = soup.find("div", id=container_id)
        if not div:
            print(f"No <div id='{container_id}'> found.")
            return []
        for el in div.find_all(["img", "a"]):
            src = el.get("src") or el.get("href") or ""
            if "javascript:" in src:
                matches = re.findall(r"'(https?://[^']+)'", src)
                urls.extend(m for m in matches if "xl" in m.lower())
            elif "xl" in src.lower():
                full = src if src.startswith(("http://", "https://")) else urljoin(listing_url, src)
                urls.append(full)
        return list(dict.fromkeys(urls))
    
    elif dealer == "ftlgr":
        # Main image
        main_img = soup.find("img", class_="mainimage")
        if main_img and main_img.get("src") and not main_img["src"].startswith("data:"):
            href = urljoin(listing_url, main_img["src"])
            urls.append(href)
        # Carousel images
        car_items = soup.find_all("div", class_="carousel-item")
        for c in car_items:
            img = c.find("img", class_="thumb")
            if img and img.get("src"):
                thumb_url = img["src"]
                full_url = thumb_url.replace("/TH_", "/")
                full_url = urljoin(listing_url, full_url)
                urls.append(full_url)
        return urls
    
    elif dealer == "fyda":
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        import time

        def get_driver():
            opts = webdriver.ChromeOptions()
            opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-software-rasterizer")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-infobars")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            return webdriver.Chrome(options=opts)

        image_urls = []
        driver = None
        try:
            driver = get_driver()
            driver.get(listing_url)
            time.sleep(5)
            # Collect URLs from div.background-image (if any)
            for div in driver.find_elements(By.CSS_SELECTOR, "div.background-image"):
                s = div.get_attribute("style")
                m = re.search(r'url\((.*?)\)', s)
                if m:
                    image_urls.append(m.group(1).strip('"\''))

            # Collect image src values from gallery and general <img> tags
            for img in driver.find_elements(By.CSS_SELECTOR, "div.galleryImages img") + driver.find_elements(By.TAG_NAME, "img"):
                src = img.get_attribute("src")
                if src and "inventory" in src:
                    image_urls.append(src)

            # Remove duplicates
            image_urls = sorted(set(image_urls))
            print(f"Extracted {len(image_urls)} images for {listing_url}")
            return image_urls

        except Exception as e:
            print(f"Error extracting images for Fyda: {e}")
            return []

        finally:
            if driver:
                driver.quit()
    
    else:
        print(f"No extraction logic for dealer: {dealer}")
        return []
