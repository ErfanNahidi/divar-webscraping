from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os
import logging
import threading
import queue
import concurrent.futures
from functools import partial
import psutil
import datetime

# Set up logging - use a single log file
log_file = "divar_scraper.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file
)
logger = logging.getLogger()
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
logger.addHandler(console_handler)

# Global variables
# Use a thread-safe queue for links to process
link_queue = queue.Queue()
# Use a thread-safe list for results
results = []
results_lock = threading.Lock()
# Progress tracking
processed_count = 0
process_lock = threading.Lock()
# CSV file name - fixed for all runs
csv_file = "divar_properties.csv"

def scroll_down(driver, scroll_pause_time=0.5):
    """Scroll down the page to load more content"""
    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Scroll down
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    # Wait to load page
    time.sleep(scroll_pause_time)
    
    # Calculate new scroll height and compare with last scroll height
    new_height = driver.execute_script("return document.body.scrollHeight")
    
    # Return True if more content was loaded
    return new_height > last_height

def extract_listing_links(driver, existing_links=None):
    """Extract listing links from the current page"""
    if existing_links is None:
        existing_links = set()
        
    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = soup.find_all("a", href=True)
    
    # Filter the relevant links (specific to property listings)
    new_links = [link['href'] for link in links if "/v/" in link['href']]
    
    # Convert relative links to absolute URLs
    full_links = [f"https://divar.ir{link}" for link in new_links]
    
    # Add new links to the existing set (to avoid duplicates)
    original_count = len(existing_links)
    existing_links.update(full_links)
    new_count = len(existing_links)
    
    # Return the set of links and how many new ones were found
    return existing_links, new_count - original_count

def create_driver(headless=True, use_chrome=False):
    """Create and return a configured WebDriver instance"""
    if use_chrome:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        # Enable faster page loading by disabling images
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(options=options)
    else:
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/89.0")
        # Set preferences to disable images and other media
        firefox_profile = webdriver.FirefoxProfile()
        firefox_profile.set_preference('permissions.default.image', 2)
        firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
        driver = webdriver.Firefox(options=options)
    
    # Increase timeout for page loads but not too much (we want fast failures)
    driver.set_page_load_timeout(15)
    return driver

def extract_property_details(driver_or_page_source, link):
    """Extract details from a property listing page
    Can accept either a driver or page source directly"""
    try:
        if isinstance(driver_or_page_source, str):
            # Use the provided page source
            page_source = driver_or_page_source
        else:
            # It's a driver, need to navigate and get the page
            driver = driver_or_page_source
            driver.get(link)
            
            # Wait for the main content to load (with a short timeout for speed)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.kt-page-title__title"))
                )
            except TimeoutException:
                # Try once more with a slight delay
                time.sleep(1)
            
            page_source = driver.page_source
        
        # Parse the listing page content
        page_soup = BeautifulSoup(page_source, "html.parser")
        
        # Extract title
        try:
            name_element = page_soup.find("h1", class_="kt-page-title__title kt-page-title__title--responsive-sized")
            name_text = name_element.get_text(strip=True) if name_element else "Not found"
        except Exception as e:
            logger.debug(f"Error extracting title: {e}")
            name_text = "Error extracting title"
        
        # Initialize property details
        property_details = {
            "Title": name_text,
            "Area": "Not found",
            "Total Price": "Not found",
            "Price per Meter": "Not found",
            "Room Count": "Not found", 
            "Build Year": "Not found",
            "Floor Number": "Not found",
            "Description": "Not found",
            "URL": link,
            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Extract details from the info rows
        try:
            info_rows = page_soup.find_all("tr", class_="kt-group-row__data-row")
            for row in info_rows:
                # Extract labels and values
                labels = row.find_all("span", class_="kt-group-row-item__title")
                values = row.find_all("td", class_="kt-group-row-item kt-group-row-item__value kt-group-row-item--info-row")
                
                for i, (label, value) in enumerate(zip(labels, values)):
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)
                    
                    # Map labels to our property details dictionary
                    if "متراژ" in label_text:  # Area
                        property_details["Area"] = value_text
                    elif "ساخت" in label_text:  # Build Year
                        property_details["Build Year"] = value_text
                    elif "اتاق" in label_text:  # Room Count
                        property_details["Room Count"] = value_text
        except Exception as e:
            logger.debug(f"Error extracting property details: {e}")
        
        # Extract price, price per meter, and floor number from unexpandable rows
        try:
            unexpandable_rows = page_soup.find_all("div", class_="kt-unexpandable-row")
            for row in unexpandable_rows:
                label = row.find("p", class_="kt-unexpandable-row__title")
                value = row.find("p", class_="kt-unexpandable-row__value")
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)
                    
                    if "قیمت کل" in label_text:  # Total price
                        property_details["Total Price"] = value_text
                    elif "قیمت هر متر" in label_text:  # Price per meter
                        property_details["Price per Meter"] = value_text
                    elif "طبقه" in label_text:  # Floor number
                        property_details["Floor Number"] = value_text
        except Exception as e:
            logger.debug(f"Error extracting price information: {e}")
        
        # Extract description
        try:
            description_element = page_soup.find("p", class_="kt-description-row__text kt-description-row__text--primary")
            if description_element:
                property_details["Description"] = description_element.get_text(strip=True)
        except Exception as e:
            logger.debug(f"Error extracting description: {e}")
        
        logger.debug(f"Successfully extracted details for: {name_text}")
        return property_details
        
    except TimeoutException:
        logger.warning(f"Timeout occurred while loading {link}")
        return None
    except Exception as e:
        logger.warning(f"Error processing listing {link}: {e}")
        return None

def worker_function():
    """Worker function for each thread to process links from the queue"""
    global processed_count
    
    # Create a new driver for this thread
    driver = None
    try:
        driver = create_driver(headless=True, use_chrome=random.choice([True, False]))
        
        while True:
            try:
                # Get a link from the queue with timeout
                link = link_queue.get(timeout=5)
                
                # Process the link
                property_details = extract_property_details(driver, link)
                
                if property_details:
                    # Add to results safely
                    with results_lock:
                        results.append(property_details)
                
                # Update processed count safely
                with process_lock:
                    processed_count += 1
                
                # Mark task as done
                link_queue.task_done()
                
                # Add a small random delay between requests
                time.sleep(random.uniform(0.1, 0.5))
                
            except queue.Empty:
                # No more links to process
                break
            except Exception as e:
                logger.warning(f"Error in worker: {e}")
                # Still mark as done to prevent hanging
                try:
                    link_queue.task_done()
                except:
                    pass
    
    finally:
        # Clean up driver
        if driver:
            try:
                driver.quit()
            except:
                pass

def print_stats(start_time, target_count):
    """Print scraping statistics periodically"""
    while True:
        with process_lock:
            current_count = processed_count
        
        elapsed = time.time() - start_time
        if elapsed > 0:
            speed = current_count / elapsed
        else:
            speed = 0
        
        remaining = max(0, target_count - current_count)
        if speed > 0:
            eta = remaining / speed
        else:
            eta = 0
        
        print(f"\rProcessed: {current_count}/{target_count} ({current_count/target_count*100:.1f}%) | "
              f"Speed: {speed:.2f} listings/sec | "
              f"ETA: {int(eta//60)}m {int(eta%60)}s | "
              f"Queue: {link_queue.qsize()}          ", end="")
        
        time.sleep(1)
        
        # Exit if we've processed everything
        if current_count >= target_count or remaining <= 0:
            print()  # Add a newline
            break

def find_optimal_thread_count():
    """Determine optimal number of threads based on system resources"""
    cpu_count = psutil.cpu_count(logical=True)
    available_memory_gb = psutil.virtual_memory().available / (1024**3)
    
    # Base calculation on available resources
    # Each browser instance can use ~300MB-500MB memory
    max_by_memory = int(available_memory_gb / 0.5)  # Allow 500MB per browser
    
    # We want to leave some CPU resources for the system
    max_by_cpu = max(1, cpu_count - 1)
    
    # Take the minimum of the two limits
    optimal = min(max_by_memory, max_by_cpu)
    
    # Cap at a reasonable number to avoid IP bans
    return min(optimal, 8)  # Maximum 8 threads

def save_results_to_csv():
    """Save current results to the CSV file"""
    if not results:
        return
        
    df = pd.DataFrame(results)
    
    # Check if the file exists
    if os.path.exists(csv_file):
        # Check if file is empty or has headers
        try:
            existing_df = pd.read_csv(csv_file)
            # Append without writing the header
            df.to_csv(csv_file, mode='a', header=False, index=False)
        except pd.errors.EmptyDataError:
            # File exists but is empty, write with header
            df.to_csv(csv_file, index=False)
    else:
        # Write with header if the file doesn't exist
        df.to_csv(csv_file, index=False)
    
    logger.info(f"Saved {len(results)} results to {csv_file}")

def scroll_to_get_all_listings(driver, target_count):
    """Scroll the page to get all listings, with better handling for infinite scroll"""
    all_links = set()
    scroll_count = 0
    consecutive_no_new = 0
    max_consecutive_no_new = 5  # Stop after 5 scrolls with no new links
    max_scroll_attempts = 200  # Safety limit
    
    print("Starting to collect listing links...")
    
    while (len(all_links) < target_count and 
           scroll_count < max_scroll_attempts and 
           consecutive_no_new < max_consecutive_no_new):
        
        # Extract links from the current view
        all_links, new_links_count = extract_listing_links(driver, all_links)
        
        print(f"\rFound {len(all_links)} listings so far. Target: {target_count} | "
              f"New: +{new_links_count} | Scroll: {scroll_count}/{max_scroll_attempts} | "
              f"No new: {consecutive_no_new}/{max_consecutive_no_new}", end="")
        
        # If we have enough links, break
        if len(all_links) >= target_count:
            break
            
        # If no new links were found, increment counter
        if new_links_count == 0:
            consecutive_no_new += 1
        else:
            consecutive_no_new = 0  # Reset counter if we found new links
        
        # Every 5 scrolls, try a different scroll technique
        if scroll_count % 5 == 0:
            # Technique 1: Random partial scroll
            scroll_position = random.uniform(0.3, 0.9)
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_position});")
            time.sleep(0.7)
            
            # Technique 2: End key
            actions = ActionChains(driver)
            actions.send_keys(Keys.END)
            actions.perform()
            time.sleep(0.7)
            
            # Technique 3: Click on "load more" button if exists
            try:
                load_more_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'بیشتر') or contains(text(), 'ادامه')]")
                if load_more_buttons:
                    for button in load_more_buttons:
                        try:
                            button.click()
                            time.sleep(1)
                        except:
                            pass
            except:
                pass
        else:
            # Standard scroll
            scroll_down(driver, scroll_pause_time=0.5)
        
        # Add variation to the scroll pause time
        time.sleep(random.uniform(0.3, 0.7))
        scroll_count += 1
    
    print(f"\nFinished gathering links. Found {len(all_links)} unique listings.")
    return list(all_links)

def main():
    global processed_count, results
    
    # Ask the user how many home listings they want
    try:
        target_count = int(input("How many home listings do you want to extract? "))
        if target_count <= 0:
            print("Please enter a positive number.")
            return
    except ValueError:
        print("Please enter a valid number.")
        return
    
    # Ask for thread count or auto-determine
    try:
        thread_choice = input("How many parallel threads do you want to use? (Enter a number or 'auto'): ")
        if thread_choice.lower() == 'auto':
            thread_count = find_optimal_thread_count()
            print(f"Auto-selected {thread_count} threads based on your system resources.")
        else:
            thread_count = int(thread_choice)
            if thread_count <= 0:
                print("Using automatic thread selection instead.")
                thread_count = find_optimal_thread_count()
                print(f"Auto-selected {thread_count} threads based on your system resources.")
    except ValueError:
        print("Invalid input. Using automatic thread selection instead.")
        thread_count = find_optimal_thread_count()
        print(f"Auto-selected {thread_count} threads based on your system resources.")
        
    print(f"Starting extraction of {target_count} home listings using {thread_count} parallel threads...")
    print(f"All data will be saved to {csv_file}")
    
    # Main driver for initial page load and scrolling
    main_driver = None
    start_time = time.time()
    
    try:
        # Initialize main WebDriver
        main_driver = create_driver(headless=True, use_chrome=True)
        
        base_url = "https://divar.ir/s/tehran/buy-residential"
        
        # Load the base page
        logger.info(f"Loading base URL: {base_url}")
        print("Loading initial page...")
        main_driver.get(base_url)
        
        # Wait for the page to load and for listings to appear
        WebDriverWait(main_driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/v/']"))
        )
        
        # Better scrolling function to get all available listings
        all_links_list = scroll_to_get_all_listings(main_driver, target_count)
        
        # Limit to target count if we have more
        if len(all_links_list) > target_count:
            all_links_list = all_links_list[:target_count]
        
        print("\nPreparing for parallel extraction...")
        
        # Add all links to the queue for processing
        for link in all_links_list:
            link_queue.put(link)
        
        # Record how many links we're processing
        total_to_process = link_queue.qsize()
        
        # Create and start worker threads
        threads = []
        for _ in range(thread_count):
            t = threading.Thread(target=worker_function)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Start a thread to print stats
        stats_thread = threading.Thread(target=print_stats, args=(time.time(), total_to_process))
        stats_thread.daemon = True
        stats_thread.start()
        
        # Save results periodically
        last_save_count = 0
        save_interval = 50  # Save every 50 processed items
        
        # Monitor progress and save periodically until queue is empty
        while not link_queue.empty():
            with process_lock:
                current_count = processed_count
                
            # Save results periodically
            if current_count - last_save_count >= save_interval:
                save_results_to_csv()
                last_save_count = current_count
                
            time.sleep(2)
        
        # Wait for all tasks to be processed
        link_queue.join()
        
        # Wait for the stats thread to finish
        stats_thread.join(timeout=2)
        
        # Final save of results
        save_results_to_csv()
        
        total_time = time.time() - start_time
        avg_speed = len(results) / total_time if total_time > 0 else 0
        
        print("\n" + "="*50)
        print(f"Extraction complete!")
        print(f"Successfully scraped {len(results)} listings out of {total_to_process} found.")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average speed: {avg_speed:.2f} listings per second")
        print(f"All data saved to {csv_file}")
        print("="*50)

    except Exception as e:
        logger.critical(f"Critical error: {e}")
        print(f"An error occurred: {e}")
        # Try to save any results we have so far
        save_results_to_csv()

    finally:
        # Make sure to close the main driver
        if main_driver:
            try:
                main_driver.quit()
                logger.info("Main WebDriver closed successfully")
            except:
                logger.warning("Main WebDriver could not be closed properly")

if __name__ == "__main__":
    main()