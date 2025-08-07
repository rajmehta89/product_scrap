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
    """Clean string to safe folder/file name."""
    return re.sub(r'[^\w\-_. ]', '_', name).strip()[:60]

def get_driver():
    options = Options()
    # Uncomment to run headless
    # options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(90)
    return driver

def extract_product_media(driver, product_url):
    print(f"Visiting: {product_url}")
    driver.get(product_url)
    time.sleep(2)  # wait page load, adjust if needed

    images = set()
    spins = set()
    videos = set()

    # 1. Extract thumbnails (images inside zoom-gallery a.mz-thumb img)
    try:
        thumbs = driver.find_elements(By.CSS_SELECTOR, "div.zoom-gallery a.mz-thumb img")
        for img in thumbs:
            src = img.get_attribute("src")
            if src and ("icon" not in src and "sprite" not in src):
                full_url = src if src.startswith("http") else urljoin(product_url, src)
                images.add(full_url)
    except Exception:
        pass

    # 2. Extract gallery/main images (div.zoom-gallery-slide figure img)
    try:
        gallery_imgs = driver.find_elements(By.CSS_SELECTOR, "div.zoom-gallery-slide figure img")
        for img in gallery_imgs:
            src = img.get_attribute("src")
            if src and ("icon" not in src):
                full_url = src if src.startswith("http") else urljoin(product_url, src)
                images.add(full_url)
    except Exception:
        pass

    # 3. Extract 360 spin images (from data-magic360-options attribute)
    try:
        magic360_els = driver.find_elements(By.CSS_SELECTOR, "a.Magic360")
        for el in magic360_els:
            data = el.get_attribute("data-magic360-options")
            if data and "images:" in data:
                imgs_raw = data.split("images:", 1)[1].split(";")[0]
                spin_urls = [i.strip() for i in imgs_raw.split(" ") if i.strip()]
                for s in spin_urls:
                    full_url = urljoin(product_url, s)
                    spins.add(full_url)
    except Exception:
        pass

    # 4. Extract embedded videos (iframe inside div.zoom-gallery-slide.video-slide)
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "div.zoom-gallery-slide.video-slide iframe")
        for iframe in iframes:
            src = iframe.get_attribute("src")
            if src:
                full_url = src if src.startswith("http") else urljoin(product_url, src)
                videos.add(full_url)
    except Exception:
        pass

    return list(images), list(spins), list(videos)

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
            print(f"  ✔ Saved image {idx} at {save_path}")
        except Exception as e:
            print(f"  ✘ Failed to download {url} - {e}")

def download_spin_images(spin_urls, folder_path):
    if not spin_urls:
        return
    spin_folder = os.path.join(folder_path, "360-spin")
    os.makedirs(spin_folder, exist_ok=True)
    download_images(spin_urls, spin_folder)

def save_video_links(video_urls, folder_path):
    if not video_urls:
        return
    file_path = os.path.join(folder_path, "video_links.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        for url in video_urls:
            f.write(url + "\n")
    print(f"  ✔ Saved video links in {file_path}")

def main():
    print("=== Product Media Downloader ===")
    product_urls = []
    while True:
        url = input("Enter product URL (or 'no' to finish): ").strip()
        if url.lower() == "no" or url == "":
            break
        if not url.lower().startswith("http"):
            print("Please enter a valid http(s):// URL")
            continue
        product_urls.append(url)

    if not product_urls:
        print("No product URLs entered. Exiting.")
        return

    root_folder = input("Enter folder to save products (default: 'products_media'): ").strip()
    if not root_folder:
        root_folder = "products_media"
    os.makedirs(root_folder, exist_ok=True)

    driver = get_driver()

    try:
        for i, link in enumerate(product_urls, 1):
            print(f"\n[{i}/{len(product_urls)}] Processing product: {link}")

            # Generate a safe folder name from the last URL segment
            product_name = safe_filename(link.rstrip('/').split('/')[-1] or f"product_{i}")
            product_folder = os.path.join(root_folder, product_name)

            try:
                imgs, spins, videos = extract_product_media(driver, link)
                print(f"  Found {len(imgs)} images, {len(spins)} 360-spin images, {len(videos)} videos")

                download_images(imgs, product_folder)
                download_spin_images(spins, product_folder)
                save_video_links(videos, product_folder)

                time.sleep(1)  # polite delay between products

            except Exception as e:
                print(f"  ✘ Error processing {link}: {e}")

    finally:
        driver.quit()
        print("\nAll done!")

if __name__ == "__main__":
    main()
