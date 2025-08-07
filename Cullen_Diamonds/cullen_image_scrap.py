import os
import re
import time
from io import BytesIO

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def safe_filename(name: str) -> str:
    """Sanitize a string to a safe filename/folder."""
    return re.sub(r"[^\w\-_. ]", "_", name).strip()[:60]

def get_driver():
    options = Options()
    # Uncomment below for headless operation
    # options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(60)
    return driver

def extract_product_info_and_images(driver, product_url):
    print(f"Visiting: {product_url}")
    driver.get(product_url)
    time.sleep(2)  # or use WebDriverWait for more robust sites

    # Extract the product name from <h1> inside <section class="details svelte-jiyox7">
    product_name = None
    try:
        section = driver.find_element(By.CSS_SELECTOR, 'section.details.svelte-jiyox7')
        h1 = section.find_element(By.TAG_NAME, 'h1')
        product_name = h1.text.strip()
    except Exception as e:
        print(f"  ✘ Could not extract product name: {e}")
        product_name = None

    # Fall back to URL name if extraction fails
    if not product_name:
        product_name = "product_" + str(int(time.time()))

    product_name = safe_filename(product_name)

    # Extract main product images
    image_urls = []
    seen_src = set()
    for img in driver.find_elements(By.CSS_SELECTOR, "img.content.image.svelte-zka3ay"):
        src = img.get_attribute("src")
        if src and not src.startswith("data:") and src not in seen_src:
            image_urls.append(src)
            seen_src.add(src)
    # Optionally: grab thumbnail images too by replicating logic here

    return product_name, image_urls

def download_images(image_urls, folder_path):
    os.makedirs(folder_path, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    for idx, url in enumerate(image_urls, 1):
        try:
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content))
            save_path = os.path.join(folder_path, f"{idx}.jpg")
            img.convert("RGB").save(save_path, "JPEG")
            print(f"  ✔ Saved {save_path}")
        except Exception as e:
            print(f"  ✘ Failed to download {url} - {e}")

def main():
    print("=== Product Media Downloader ===")
    root_folder = input("Enter root download folder (default: 'products_media'): ").strip()
    if not root_folder:
        root_folder = "products_media"
    os.makedirs(root_folder, exist_ok=True)

    product_urls = []
    while True:
        url = input("Enter product URL (or 'no' to finish): ").strip()
        if url.lower() in ("no", ""):
            break
        if not url.lower().startswith("http"):
            print("Please enter a valid http(s):// URL")
            continue
        product_urls.append(url)

    if not product_urls:
        print("No product URLs entered. Exiting.")
        return

    driver = get_driver()
    try:
        for i, url in enumerate(product_urls, 1):
            print(f"\n[{i}/{len(product_urls)}] Processing: {url}")
            try:
                product_name, image_urls = extract_product_info_and_images(driver, url)
                product_folder = os.path.join(root_folder, product_name)
                print(f"  Saving images to: {product_folder}")
                if image_urls:
                    download_images(image_urls, product_folder)
                else:
                    print("  ✘ No images found!")
                time.sleep(1)
            except Exception as e:
                print(f"  ✘ Error processing {url}: {e}")
    finally:
        driver.quit()
        print("\nAll done!")

if __name__ == "__main__":
    main()
