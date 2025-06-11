# core/image_utils.py
# for now works only for jasper truck

import os
import re
from typing import List
import requests
import requests.compat
from bs4 import BeautifulSoup

def extract_image_urls_from_page(listing_url: str, container_id: str = "photos") -> List[str]:
    """
    Fetch listing_url, look for <div id=container_id>,
    grab any 'xl' URLs from <img> src or <a> href/js, and return a deduped list.
    """
    try:
        resp = requests.get(listing_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {listing_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    div = soup.find("div", id=container_id)
    if not div:
        print(f"No <div id='{container_id}'> found.")
        return []

    urls = []
    for el in div.find_all(["img", "a"]):
        src = el.get("src") or el.get("href") or ""
        # handle javascript: links
        if "javascript:" in src:
            matches = re.findall(r"'(https?://[^']+)'", src)
            urls.extend(m for m in matches if "xl" in m.lower())
        elif "xl" in src.lower():
            full = src if src.startswith(("http://", "https://")) else requests.compat.urljoin(listing_url, src)
            urls.append(full)

    # Remove duplicates, preserve order
    return list(dict.fromkeys(urls))


def download_images(image_urls: List[str], dest_folder: str, prefix: str = "") -> List[str]:
    """
    Given a list of image URLs, download each into dest_folder.
    Files will be named prefix + '1.ext', prefix + '2.ext', ...
    Returns list of saved file paths.
    """
    os.makedirs(dest_folder, exist_ok=True)
    saved_paths = []

    for idx, url in enumerate(image_urls, start=1):
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        filename = f"{prefix}{idx}{ext}"
        full_path = os.path.join(dest_folder, filename)

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with open(full_path, "wb") as f:
                f.write(resp.content)
            saved_paths.append(full_path)
            print(f"Downloaded image {idx} → {full_path}")
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
