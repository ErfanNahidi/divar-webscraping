from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import random

# Setup for headless Chrome
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")  # Optional for better performance on some systems

# Initialize WebDriver
driver = webdriver.Chrome(options=options)
base_url = "https://divar.ir/s/tehran/buy-residential"

# Load the base page
driver.get(base_url)
time.sleep(3)  # Wait for the page to load completely

# Parse the page content with BeautifulSoup
soup = BeautifulSoup(driver.page_source, "html.parser")

# Find all links on the page
links = soup.find_all("a", href=True)

# Filter the relevant links (specific to property listings)
filtered_links = [link['href'] for link in links if "/v/" in link['href']]

# Convert relative links to absolute URLs
full_links = [f"https://divar.ir{link}" for link in filtered_links]

# Visit each filtered link
for link in full_links:
    time.sleep(random.uniform(2, 5))  # Random delay between requests
    print(f"Visiting: {link}")
    
    driver.get(link)
    time.sleep(2)  # Wait for the listing page to load

    # Parse the listing page content
    page_soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Extract area information
    area = page_soup.find("td", class_="kt-group-row-item kt-group-row-item__value kt-group-row-item--info-row")
    area_text = area.get_text(strip=True) if area else "Area not found"
    
    # Extract price information
    price = page_soup.find("p", class_="kt-unexpandable-row__value")
    price_text = price.get_text(strip=True) if price else "Price not found"
    
    print(f"Area: {area_text}")
    print(f"Price: {price_text}")
    print("-" * 50)

# Close the WebDriver
driver.quit()
