

# 🏘️ Divar Property Scraper

A high-performance, multi-threaded web scraper built in Python to extract real estate listings from [Divar.ir](https://divar.ir), Iran’s leading classified ads platform. This tool uses `Selenium` and `BeautifulSoup` to automate data extraction, supporting both Firefox and Chrome in headless mode.

---

## 🚀 Features

- **Multi-threaded scraping** with intelligent load distribution
- **Adaptive thread count** based on system CPU/RAM
- **Smart infinite scrolling** with random pauses, end-key actions, and load-more button interaction
- **BeautifulSoup parsing** for accurate content extraction
- **Live progress tracking**: ETA, speed, and completion metrics
- **Periodic auto-saving** of data to prevent loss
- **Real-time logging** to both console and file (`divar_scraper.log`)
- Outputs structured data to `divar_properties.csv`

---

## 📦 Requirements

- Python 3.7+
- Google Chrome or Mozilla Firefox
- Recommended: virtual environment

Install dependencies:

```bash
pip install -r requirements.txt
```

> Make sure `chromedriver` or `geckodriver` is installed and added to your PATH.

---

## 🛠️ Usage

```bash
python main.py
```

You will be prompted to enter:
- Number of listings to extract (e.g., 300)
- Number of threads to use (or type `auto` for smart detection)

---

## 🧪 Extracted Fields

Each property will include:
- `Title`
- `Area`
- `Total Price`
- `Price per Meter`
- `Room Count`
- `Build Year`
- `Floor Number`
- `Description`
- `URL`
- `Timestamp`

---

## ⚙️ How It Works

1. Opens Divar Tehran buy-residential page
2. Performs infinite scrolling & interaction
3. Extracts and stores all property URLs
4. Spawns multiple threads, each with its own browser instance
5. Scrapes structured data from each page
6. Saves results to `CSV` at regular intervals

---

## 🧠 Optimization Logic

- Thread count is dynamically calculated based on:
  - Available CPU cores
  - Free system memory
  - Hard cap to avoid IP bans or memory overuse

---

## 📁 Output Example

```csv
Title, Area, Total Price, Price per Meter, Room Count, Build Year, Floor Number, Description, URL, Timestamp
...
```

Developed with love by **Erfan** 🧠⚙️  
Passionate about data science, software engineering, and behavioral intelligence.

