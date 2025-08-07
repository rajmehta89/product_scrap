from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os

def get_all_product_links(url, max_idle_cycles=6, scroll_increment=300, scroll_delay=0.7):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    product_links = set()

    try:
        driver.get(url)
        print("Page loaded. Starting aggressive scrolling to load all products (press Ctrl+C to stop)...\n")

        idle_cycles = 0
        last_count = 0

        while True:
            try:
                # Get current scroll height of the document
                scroll_height = driver.execute_script("return document.body.scrollHeight")
                current_scroll_pos = 0

                # Scroll down gradually to bottom
                while current_scroll_pos < scroll_height:
                    driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                    current_scroll_pos += scroll_increment
                    time.sleep(scroll_delay)

                # Optional jiggle scroll: up then down to re-trigger lazy loading
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                time.sleep(2)  # Let page catch up after jiggle scroll

                # Gather product links (adjust selector if needed)
                product_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
                for elem in product_elements:
                    link = elem.get_attribute("href")
                    if link and link.startswith("http"):
                        product_links.add(link)

                print(f"Found {len(product_links)} unique product links so far...")

                if len(product_links) == last_count:
                    idle_cycles += 1
                    print(f"No new products loaded, idle count: {idle_cycles}/{max_idle_cycles}\n")
                    if idle_cycles >= max_idle_cycles:
                        print("Reached stable number of products, stopping scroll.")
                        break
                else:
                    idle_cycles = 0
                    last_count = len(product_links)

            except Exception as e:
                print(f"❌ Error during scrolling or link extraction: {e}")
                time.sleep(5)

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user.")
    finally:
        driver.quit()

        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_path):
            os.makedirs(desktop_path)
            print(f"Created Desktop directory at {desktop_path}")

        file_path = os.path.join(desktop_path, "links.txt")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(",".join(product_links))
            print(f"\n✅ Total products found: {len(product_links)}")
            print(f"Links saved to: {file_path}")
        except Exception as e:
            print(f"❌ Failed to save links to file: {e}")

if __name__ == "__main__":
    url = input("Enter the product listing URL: ").strip()
    get_all_product_links(url)
