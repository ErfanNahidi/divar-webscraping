from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os

# Setup for headless browser
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")

# Initialize WebDriver
driver = webdriver.Firefox(options=options)
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

# Initialize a list for storing data
data = []

# Visit each filtered link
for link in full_links:
    time.sleep(random.uniform(2, 5))  # Random delay between requests
    print(f"Visiting: {link}")
    
    driver.get(link)
    time.sleep(4)  # Wait for the listing page to load

    # Parse the listing page content
    page_soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Extract details
    name_reportaj = page_soup.find("h1", class_="kt-page-title__title kt-page-title__title--responsive-sized")
    name_reportaj_text = name_reportaj.get_text(strip=True) if name_reportaj else "not found"

    # Extract area, build year, and floor number
    info_row = page_soup.find("tr", class_="kt-group-row__data-row")
    if info_row:
        info_values = info_row.find_all("td", class_="kt-group-row-item kt-group-row-item__value kt-group-row-item--info-row")
        if len(info_values) >= 3:  # Ensure enough data is present
            area_text = info_values[0].get_text(strip=True)  # Area
            build_year_text = info_values[1].get_text(strip=True)  # Build year
            room_number_text = info_values[2].get_text(strip=True)  # Room count (not floor)
        else:
            area_text = "Area not found"
            build_year_text = "Build Year not found"
            room_number_text = "Room Count not found"
    else:
        area_text = "Area not found"
        build_year_text = "Build Year not found"
        room_number_text = "Room Count not found"

    # Extract price, price per meter, and floor number
    price_tags = page_soup.find_all("p", class_="kt-unexpandable-row__value")
    if len(price_tags) >= 3:
        try:
            total_price_text = price_tags[0].get_text(strip=True)  # Price in total
            per_meter_price_text = price_tags[1].get_text(strip=True)  # Price per meter
            floor_number_text = price_tags[2].get_text(strip=True)  # Floor number
        except Exception as e:
            total_price_text = "Price not found"
            per_meter_price_text = "Price per meter not found"
            floor_number_text = "Floor number not found"
            print(f"Error extracting price info: {e}")
    else:
        total_price_text = "Price not found"
        per_meter_price_text = "Price per meter not found"
        floor_number_text = "Floor number not found"

    # Extract description
    description_text = "Description not found"  # Default value
    description_tag = page_soup.find("p", class_="kt-description-row__text kt-description-row__text--primary")
    if description_tag:
        description_text = description_tag.get_text(strip=True)

    # Add data to the list for each listing
    data.append({
        "Title": name_reportaj_text,
        "Area": area_text,
        "Total Price": total_price_text,
        "Price per Meter": per_meter_price_text,
        "Room Count": room_number_text,
        "Build Year": build_year_text,
        "Description": description_text,
        "URL": link
    })

    print(f"Extracted: {name_reportaj_text}, {total_price_text}, {area_text}")
    print("-" * 50)

# Close the WebDriver
driver.quit()

# Convert data to a DataFrame
df = pd.DataFrame(data)

# Save to CSV for further analysis
csv_file = "divar_properties.csv"

# Check if the file exists
if os.path.exists(csv_file):
    # Append without writing the header
    df.to_csv(csv_file, mode='a', header=False, index=False)
else:
    # Write with header if the file doesn't exist
    df.to_csv(csv_file, index=False)

print(f"Data saved to {csv_file}")
