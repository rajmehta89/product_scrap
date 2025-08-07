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
from selenium.common.exceptions import TimeoutException, WebDriverException
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
    # Uncomment for headless mode
    # chrome_options.add_argument('--headless')
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(90)
        return driver
    except Exception as e:
        print("Could not initiate browser: ", e)
        exit(1)

def get_product_links_from_collection(driver, collection_url):
    print(f"Loading collection page: {collection_url}")
    try:
        driver.get(collection_url)
    except Exception as e:
        print(f"  ⚠️ Error: could not load collection page, skipping. [{e}]")
        return []
    time.sleep(3)
    links = set()
    selectors = [
        "a.full-unstyled-link",
        "a.product-title",
        "a.grid-view-item__link",
        "a.productitem--image-link",
        "a[href*='/products/']"
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                href = el.get_attribute('href')
                if href and '/products/' in href:
                    links.add(href.split('?')[0])
        except Exception:
            continue
    print(f"Found {len(links)} product links.")
    return sorted(list(links))

def get_gallery_images(driver, product_url):
    # List of gallery containers for Shopify and similar
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
    used_names = set()
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
            used_names.add(os.path.basename(new_path).lower())
            print(f"    ✔ {os.path.abspath(new_path)} [{img.size}]")
            count += 1
        except Exception as e:
            print(f"    ✘ Failed: {img_url} [{repr(e)}]")
            continue
    # Remove other files that do not match the pattern <number>.jpg
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
    print("=== Shopify/Porter Lyons Collection Product Image & Renamer Scraper ===")
    collection_url = robust_input("Enter FULL collection page URL: ")
    if not collection_url.lower().startswith("http"):
        print("Please enter a valid collection page URL (starting with http...)")
        return
    folder_path = robust_input("Enter base folder to save images (default: 'downloaded_collection'): ", default='downloaded_collection')
    os.makedirs(folder_path, exist_ok=True)

    driver = get_driver()
    try:
        links = get_product_links_from_collection(driver, collection_url)
        if not links:
            print("No products found on collection page.")
            return
        print(f"Found {len(links)} products. Starting download...\n")
        for idx, product_link in enumerate(links, 1):
            print(f"[{idx}/{len(links)}] {product_link}")
            try:
                get_product_images(product_link, driver, folder_path)
            except Exception as e:
                print(f"  ⚠️ Fatal error with {product_link}: {e}")
                continue
            # Restart driver every 10 products to avoid resource leaks
            if idx % 10 == 0:
                try:
                    driver.quit()
                except: pass
                driver = get_driver()
            time.sleep(2)  # Be nice to the shop and avoid rate-limits
        print("=== ALL DONE! ===")
    finally:
        try:
            driver.quit()
        except: pass

if __name__ == "__main__":
    main()
