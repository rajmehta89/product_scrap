import os
import re
import time
import traceback
from io import BytesIO
from PIL import Image
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, urljoin

def safe_filename(s):
    return re.sub(r'[^\w\-_\. ]', '_', s.strip())

def robust_input(prompt, default=None):
    try:
        value = input(prompt).strip()
        return value if value else (default if default is not None else "")
    except Exception:
        return default if default is not None else ""

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--window-size=1400,1000')
    # chrome_options.add_argument('--headless') # Uncomment for headless mode
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(90)
        return driver
    except Exception as e:
        print("Could not initiate browser: ", e)
        exit(1)

def get_gallery_images(driver, product_url):
    gallery_selectors = [
        ".product-gallery, .Product__Slideshow, .product-media--container, .main-image, .carousel, .product__media-list",
        ".image-slide.carousel-cell",
        "div[data-image-id]",
        ".product-images__thumbnails",
        "div[class*='gallery']",
        "ul[role='list']",
    ]
    images = set()
    found = False
    for gallery_sel in gallery_selectors:
        try:
            containers = driver.find_elements(By.CSS_SELECTOR, gallery_sel)
            for container in containers:
                imgs = container.find_elements(By.TAG_NAME, "img")
                for el in imgs:
                    for attr in ["srcset", "data-srcset", "data-src", "src"]:
                        url = el.get_attribute(attr)
                        if url:
                            if ',' in url:
                                url = url.split(',')[-1].split()[0]
                            url = url.strip()
                            if url.startswith("//"):
                                url = "https:" + url
                            elif url.startswith("/"):
                                parsed = urlparse(product_url)
                                url = urljoin(f"{parsed.scheme}://{parsed.netloc}", url)
                            if not any(x in url.lower() for x in ['icon', 'placeholder', 'logo', '.svg', '.ico', 'avatar']):
                                images.add(url)
                                found = True
                if found and images:
                    break
            if found:
                break
        except Exception:
            continue
    if not images:
        try:
            thumbs = driver.find_elements(By.CSS_SELECTOR, "ul[class*='thumbnails'] img, .thumbnails img")
            for el in thumbs:
                for attr in ["srcset", "data-srcset", "data-src", "src"]:
                    url = el.get_attribute(attr)
                    if url:
                        if ',' in url:
                            url = url.split(',')[-1].split()[0]
                        url = url.strip()
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            parsed = urlparse(product_url)
                            url = urljoin(f"{parsed.scheme}://{parsed.netloc}", url)
                        if not any(x in url.lower() for x in ['icon', 'placeholder', 'logo', '.svg', '.ico', 'avatar']):
                            images.add(url)
        except Exception:
            pass
    return sorted(list(images))

def get_product_name(driver, product_url):
    try:
        name_elem = driver.find_element(By.CSS_SELECTOR, 'h1')
        name = name_elem.text.strip()
        if name: return name
    except: pass
    return product_url.rstrip('/').rsplit('/',1)[-1].replace('-', ' ').title()

def download_and_number_images(img_urls, save_folder):
    count = 1
    headers = {'User-Agent': "Mozilla/5.0"}
    for img_url in img_urls:
        try:
            resp = requests.get(img_url, headers=headers, timeout=45)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            if img.width < 100 or img.height < 100:
                continue
            new_path = os.path.join(save_folder, f"{count}.jpg")
            img = img.convert("RGB")
            img.save(new_path, "JPEG")
            print(f"    ✔ {os.path.abspath(new_path)} [{img.size}]")
            count += 1
        except Exception as e:
            print(f"    ✘ Failed: {img_url} [{repr(e)}]")
            continue
    # Remove other files not matching <number>.jpg
    for file in os.listdir(save_folder):
        if not re.match(r'^\d+\.jpg$', file.lower()):
            try:
                os.remove(os.path.join(save_folder, file))
            except Exception as e:
                print(f"    ⚠️ Couldn't delete: {file} [{repr(e)}]")

def get_product_images(product_url, driver, base_save_dir):
    print(f"  Visiting product: {product_url}")
    try:
        try:
            driver.set_page_load_timeout(70)
            driver.get(product_url)
        except TimeoutException:
            print(f"    ⚠️ Timeout while loading {product_url}. Skipping.")
            return
        except Exception as e:
            print(f"    ⚠️ Error loading {product_url}: {repr(e)}")
            return
        time.sleep(2)
        product_name = get_product_name(driver, product_url)
        folder_name = safe_filename(product_name)[:60]
        product_folder = os.path.join(base_save_dir, folder_name)
        os.makedirs(product_folder, exist_ok=True)
        img_urls = get_gallery_images(driver, product_url)
        print(f"    {len(img_urls)} gallery images found for '{product_name}'")
        if img_urls:
            download_and_number_images(img_urls, product_folder)
            print(f"    >> Saved in folder: {os.path.abspath(product_folder)}\n")
        else:
            print(f"    !! No images found for {product_name}\n")
    except Exception as e:
        print(f"    ⚠️ Unhandled error: {e}")
        traceback.print_exc()

def main():
    print("=== Product Direct Link Image Downloader ===")
    base_folder = robust_input("Enter the base folder where images should be saved (default: 'downloaded_products'): ", default='downloaded_products')
    os.makedirs(base_folder, exist_ok=True)

    # Ask for product links, one per line, until the user presses Enter on a blank line
    product_links = []
    print("Enter each product link directly. When done, just press Enter on a blank line.")
    while True:
        product_url = input("Enter the product link (or just press Enter to finish): ").strip()
        if not product_url:
            break
        if not product_url.lower().startswith("http"):
            print("  Invalid URL, must start with http.")
            continue
        product_links.append(product_url)
    if not product_links:
        print("No product links were entered. Exiting.")
        return

    driver = get_driver()
    try:
        print(f"\nWill now process {len(product_links)} products...\n")
        for idx, url in enumerate(product_links, 1):
            print(f"[{idx}/{len(product_links)}] {url}")
            try:
                get_product_images(url, driver, base_folder)
            except Exception as e:
                print(f"  ⚠️ Fatal error with {url}: {e}")
                continue
            time.sleep(2)  # Friendly pause
        print("=== ALL DONE! ===")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
