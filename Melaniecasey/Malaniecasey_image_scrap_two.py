import os
import re
import time
from io import BytesIO
from urllib.parse import urlparse, urljoin

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


def safe_filename(name: str) -> str:
    return re.sub(r'[^\w\-_. ]', '_', name).strip()[:60]


def get_driver():
    options = Options()
    # Uncomment below for headless mode if desired
    # options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(90)
    return driver


def extract_gallery_images(driver, product_url):
    images = []
    try:
        gallery = driver.find_element(By.CSS_SELECTOR, "div.image-container.sliding-images.pinchable-container")
        slides = gallery.find_elements(By.CSS_SELECTOR, "div[data-index]")
    except NoSuchElementException:
        print("  ⚠️ Gallery container not found.")
        return []

    indexed_slides = []
    for slide in slides:
        try:
            idx = int(slide.get_attribute("data-index"))
            indexed_slides.append((idx, slide))
        except:
            continue

    indexed_slides.sort(key=lambda x: x[0])
    for _, slide in indexed_slides:
        img_url = None
        try:
            img_elem = slide.find_element(By.TAG_NAME, "img")
            srcset = img_elem.get_attribute("srcset")
            if srcset:
                # Select largest image in srcset by width
                sources = []
                for src in srcset.split(","):
                    url_part = src.strip().split(" ")[0]
                    width_match = re.search(r"(\d+)w", src)
                    width = int(width_match.group(1)) if width_match else 0
                    sources.append((width, url_part))
                sources.sort(reverse=True, key=lambda x: x[0])
                img_url = sources[0][1]
            else:
                for attr in ["data-src", "data-lazy-src", "src"]:
                    val = img_elem.get_attribute(attr)
                    if val:
                        img_url = val
                        break
            if img_url:
                img_url = img_url.strip()
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                elif img_url.startswith("/"):
                    parsed = urlparse(product_url)
                    img_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", img_url)

                if not any(x in img_url.lower() for x in ['icon', 'sprite', 'placeholder', 'avatar']):
                    images.append(img_url)
        except NoSuchElementException:
            continue

    # Remove duplicates but keep order
    seen = set()
    filtered_images = []
    for url in images:
        if url not in seen:
            seen.add(url)
            filtered_images.append(url)

    return filtered_images


def download_images(img_urls, folder_path):
    os.makedirs(folder_path, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    for idx, img_url in enumerate(img_urls, 1):
        try:
            r = requests.get(img_url, headers=headers, timeout=60)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content))
            save_path = os.path.join(folder_path, f"{idx}.jpg")
            img.convert("RGB").save(save_path, "JPEG")
            print(f"      ✔ Saved image {idx} at {save_path}")
        except Exception as e:
            print(f"      ✘ Failed to download {img_url}: {e}")


def scrape_products(product_urls, save_root_folder):
    driver = get_driver()
    try:
        for idx, url in enumerate(product_urls, 1):
            print(f"\n[{idx}/{len(product_urls)}] Processing: {url}")
            try:
                driver.get(url)
                time.sleep(3)  # Let page load fully
            except TimeoutException:
                print("    ⚠️ Timeout loading page, skipping...")
                continue

            # Use product name from URL slug
            product_name = safe_filename(url.rstrip('/').split('/')[-1] or "Unknown_Product")
            print(f"    Product name: {product_name}")

            img_urls = extract_gallery_images(driver, url)
            if not img_urls:
                print("    ⚠️ No gallery images found, skipping...")
                continue

            save_folder = os.path.join(save_root_folder, product_name)
            download_images(img_urls, save_folder)

            time.sleep(2)  # polite delay between products
    finally:
        driver.quit()


def main():
    print("=== Product Images Batch Scraper ===")
    input_urls = input("Enter comma-separated product URLs:\n").strip()
    if not input_urls:
        print("No URLs entered, exiting.")
        return

    # Split by comma, clean extra spaces, filter out empty strings
    product_urls = [url.strip() for url in input_urls.split(",") if url.strip()]
    if not product_urls:
        print("No valid URLs parsed, exiting.")
        return

    save_folder = input("Enter folder to save images (default: 'downloaded_products'): ").strip()
    if not save_folder:
        save_folder = "downloaded_products"
    os.makedirs(save_folder, exist_ok=True)

    print(f"\nStarting to scrape {len(product_urls)} products...")
    scrape_products(product_urls, save_folder)
    print("\nAll done!")


if __name__ == "__main__":
    main()
