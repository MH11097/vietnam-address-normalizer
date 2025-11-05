# -*- coding: utf-8 -*-
"""
Vietnamese Administrative Division Crawler

Crawls administrative division data (provinces, districts, wards) from
https://danhmuchanhchinh.gso.gov.vn/Lich_Su_Moi.aspx

Output: CSV files with historical snapshots (monthly from 01/2022 to current)
"""

import os
import sys
import time
import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# Constants
BASE_URL = "https://danhmuchanhchinh.gso.gov.vn/Lich_Su_Moi.aspx"
OUTPUT_DIR = Path(__file__).parent / "data" / "crawled_admin_divisions"
DELAY_BETWEEN_REQUESTS = 1  # seconds (reduced from 2 to 1)
MAX_RETRIES = 3
PAGE_LOAD_WAIT = 1.5  # seconds to wait for page transitions

# Element IDs (DevExpress controls)
ADMIN_LEVEL_INPUT_ID = "ctl00_PlaceHolderMain_cmbCap_I"
ADMIN_LEVEL_DROPDOWN_ID = "ctl00_PlaceHolderMain_cmbCap"
DATE_INPUT_ID = "ctl00_PlaceHolderMain_txtNgay_I"
SUBMIT_BUTTON_ID = "ctl00_PlaceHolderMain_ASPxButton1"


class AdminDivisionCrawler:
    """Crawler for Vietnamese administrative divisions from GSO website"""

    def __init__(self, headless: bool = False, output_dir: Path = OUTPUT_DIR):
        """
        Initialize crawler with Selenium WebDriver

        Args:
            headless: Run browser in headless mode (no GUI)
            output_dir: Directory to save CSV files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup Chrome options
        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Initialize WebDriver
        print("Initializing Chrome WebDriver...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            print("Browser closed.")

    def navigate_to_page(self):
        """Navigate to the admin division page"""
        print(f"Navigating to {BASE_URL}...")
        self.driver.get(BASE_URL)
        time.sleep(2)  # Wait for page load

    def select_admin_level(self, level: str = "Xã"):
        """
        Select administrative level from DevExpress dropdown

        Args:
            level: "Tỉnh", "Huyện", or "Xã" (default: "Xã" for most detailed data)
        """
        try:
            # Wait for input to be present
            input_element = self.wait.until(
                EC.presence_of_element_located((By.ID, ADMIN_LEVEL_INPUT_ID))
            )

            # Click to open dropdown
            input_element.click()
            time.sleep(1)

            # Find and click the option in the dropdown list
            # DevExpress creates a popup div with options
            dropdown_items = self.driver.find_elements(By.CSS_SELECTOR, "td.dxeListBoxItem")

            for item in dropdown_items:
                if level in item.text:
                    item.click()
                    print(f"Selected admin level: {level}")
                    time.sleep(1)
                    return

            # Fallback: try using JavaScript to set value
            self.driver.execute_script(
                f"document.getElementById('{ADMIN_LEVEL_INPUT_ID}').value = '{level}';"
            )
            print(f"Selected admin level (fallback): {level}")
            time.sleep(1)

        except Exception as e:
            print(f"Error selecting admin level: {e}")
            raise

    def input_date(self, date_str: str):
        """
        Input date into the DevExpress date field

        Args:
            date_str: Date in format "dd/MM/yyyy" (e.g., "01/01/2022")
        """
        try:
            # Find date input by ID
            date_input = self.wait.until(
                EC.presence_of_element_located((By.ID, DATE_INPUT_ID))
            )

            # Clear and enter date
            date_input.clear()
            date_input.send_keys(date_str)

            print(f"Entered date: {date_str}")
            time.sleep(1)

        except Exception as e:
            print(f"Error inputting date: {e}")
            raise

    def submit_form(self):
        """Submit the form and wait for results"""
        try:
            # Find DevExpress button by ID
            submit_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, SUBMIT_BUTTON_ID))
            )

            submit_button.click()
            print("Form submitted. Waiting for results...")
            time.sleep(3)  # Wait for table to load

        except Exception as e:
            print(f"Error submitting form: {e}")
            # Fallback: try to find button with text "Thực Hiện"
            try:
                buttons = self.driver.find_elements(By.TAG_NAME, "div")
                for button in buttons:
                    if "Thực Hiện" in button.text or "thực hiện" in button.text.lower():
                        button.click()
                        print("Form submitted (fallback). Waiting for results...")
                        time.sleep(3)
                        return
            except Exception as fallback_error:
                print(f"Fallback failed: {fallback_error}")
            raise

    def get_total_pages(self) -> int:
        """Get total number of pages from pagination"""
        try:
            # Find pagination summary text: "Trang 1 / 14 (10541 dòng)"
            pager = self.driver.find_element(By.CLASS_NAME, "dxpSummary_Office2003_Blue")
            text = pager.text  # e.g., "Trang 1 / 14 (10541 dòng)"

            # Extract total pages
            if "/" in text:
                parts = text.split("/")
                if len(parts) >= 2:
                    total_pages = int(parts[1].split()[0].strip())
                    print(f"Total pages: {total_pages}")
                    return total_pages

            return 1
        except:
            return 1

    def click_next_page(self) -> bool:
        """Click next page button. Returns True if successful, False if no more pages"""
        try:
            # Try multiple approaches to find Next button

            # Approach 1: Find by onclick attribute
            try:
                next_buttons = self.driver.find_elements(By.XPATH, "//td[@onclick and contains(@onclick, 'PBN')]")
                if next_buttons:
                    next_button = next_buttons[0]
                    # Check if disabled
                    if "dxpDisabled" not in next_button.get_attribute("class"):
                        next_button.click()
                        print("Clicked next page button")
                        time.sleep(PAGE_LOAD_WAIT)  # Reduced wait time
                        return True
                    else:
                        print("Next button is disabled (last page)")
                        return False
            except Exception as e1:
                print(f"Approach 1 failed: {e1}")

            # Approach 2: Find by image alt text
            try:
                next_button = self.driver.find_element(By.XPATH, "//img[@alt='Next']/parent::td")
                if "dxpDisabled" not in next_button.get_attribute("class"):
                    next_button.click()
                    print("Clicked next page button (approach 2)")
                    time.sleep(PAGE_LOAD_WAIT)
                    return True
                else:
                    print("Next button is disabled")
                    return False
            except Exception as e2:
                print(f"Approach 2 failed: {e2}")

            return False
        except Exception as e:
            print(f"Error clicking next page: {e}")
            return False

    def extract_table_data(self) -> List[Dict[str, str]]:
        """
        Extract data from ALL pages of the results table

        Returns:
            List of dictionaries containing admin division data from all pages
        """
        all_data = []

        try:
            # Get total number of pages
            total_pages = self.get_total_pages()

            # Extract data from each page
            for page_num in range(1, total_pages + 1):
                print(f"Extracting page {page_num}/{total_pages}...")

                # Wait for the main data grid table (DevExpress grid)
                table = self.wait.until(
                    EC.presence_of_element_located((By.ID, "ctl00_PlaceHolderMain_grid3_DXMainTable"))
                )

                # Find all rows (ALL are data rows, no header in this table)
                rows = table.find_elements(By.TAG_NAME, "tr")

                if len(rows) == 0:
                    print(f"Warning: No data rows on page {page_num}")
                    continue

                # Extract headers (only on first page)
                if page_num == 1:
                    # Headers are in a separate header table, not in the data table
                    # Look for the header table by finding parent table structure
                    try:
                        # Try to find header row in the grid's header section
                        header_table = self.driver.find_element(
                            By.XPATH,
                            "//table[@id='ctl00_PlaceHolderMain_grid3_DXHeadersRow0']"
                        )
                        th_elements = header_table.find_elements(By.TAG_NAME, "td")
                        raw_headers = [th.text.strip() for th in th_elements]
                    except:
                        # Fallback: find any row with class containing "Header"
                        try:
                            header_rows = self.driver.find_elements(
                                By.XPATH,
                                "//tr[contains(@class, 'Header') or contains(@id, 'Header')]"
                            )
                            if header_rows:
                                th_elements = header_rows[0].find_elements(By.TAG_NAME, "td")
                                if not th_elements:
                                    th_elements = header_rows[0].find_elements(By.TAG_NAME, "th")
                                raw_headers = [th.text.strip() for th in th_elements]
                            else:
                                # Last resort: use generic column names
                                num_cols = len(rows[0].find_elements(By.TAG_NAME, "td")) if rows else 9
                                raw_headers = [f"column_{i}" for i in range(num_cols)]
                        except:
                            # Last resort: count columns from first data row
                            num_cols = len(rows[0].find_elements(By.TAG_NAME, "td")) if rows else 9
                            raw_headers = [f"column_{i}" for i in range(num_cols)]

                    # Create headers with fallback names for empty strings
                    self.headers = []
                    for i, h in enumerate(raw_headers):
                        if h:
                            self.headers.append(h)
                        else:
                            self.headers.append(f"column_{i}")

                    print(f"Found {len(self.headers)} columns")
                    print(f"Headers: {self.headers}")  # Debug: show all headers

                # Extract data rows using JavaScript for maximum speed
                page_data = []
                print(f"Processing {len(rows)} data rows...")

                # Use JavaScript to extract all data (ALL rows are data, no header in this table)
                js_script = """
                var table = arguments[0];
                var rows = table.querySelectorAll('tr');
                var data = [];

                for (var i = 0; i < rows.length; i++) {
                    var cells = rows[i].querySelectorAll('td');
                    if (cells.length === 0) {
                        continue;
                    }

                    var rowData = [];
                    for (var j = 0; j < cells.length; j++) {
                        rowData.push(cells[j].textContent.trim());
                    }
                    data.push(rowData);
                }
                return data;
                """

                try:
                    rows_data = self.driver.execute_script(js_script, table)

                    for row_values in rows_data:
                        if not row_values:
                            continue

                        row_data = {}
                        for i, value in enumerate(row_values):
                            header = self.headers[i] if i < len(self.headers) else f"column_{i}"
                            row_data[header] = value

                        page_data.append(row_data)

                except Exception as e:
                    print(f"JavaScript extraction failed, falling back to slow method: {e}")
                    # Fallback to old method (ALL rows are data)
                    for row_idx, row in enumerate(rows, 1):
                        if row_idx % 100 == 0:
                            print(f"  Processed {row_idx} rows...")

                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) == 0:
                            continue

                        row_data = {}
                        for i, cell in enumerate(cells):
                            header = self.headers[i] if i < len(self.headers) else f"column_{i}"
                            try:
                                cell_text = cell.get_attribute('textContent')
                                if cell_text is None:
                                    cell_text = ""
                            except:
                                cell_text = ""
                            row_data[header] = cell_text.strip()

                        page_data.append(row_data)

                print(f"Extracted {len(page_data)} rows from page {page_num}")
                all_data.extend(page_data)

                # Click next page if not last page
                if page_num < total_pages:
                    if not self.click_next_page():
                        print(f"Could not go to next page. Stopping at page {page_num}")
                        break

            print(f"Total extracted: {len(all_data)} rows from {page_num} pages")
            return all_data

        except TimeoutException:
            print("Timeout waiting for table to load")
            return all_data
        except Exception as e:
            print(f"Error extracting table data: {e}")
            import traceback
            traceback.print_exc()
            return all_data

    def crawl_for_date(self, date_str: str, level: str = "Xã", retry: int = 0) -> Optional[List[Dict[str, str]]]:
        """
        Crawl data for a specific date

        Args:
            date_str: Date in format "dd/MM/yyyy"
            level: Administrative level
            retry: Current retry attempt

        Returns:
            List of extracted data or None if failed
        """
        try:
            self.navigate_to_page()
            self.select_admin_level(level)
            self.input_date(date_str)
            self.submit_form()

            data = self.extract_table_data()

            if not data and retry < MAX_RETRIES:
                print(f"No data found. Retrying ({retry + 1}/{MAX_RETRIES})...")
                time.sleep(DELAY_BETWEEN_REQUESTS * 2)
                return self.crawl_for_date(date_str, level, retry + 1)

            return data

        except Exception as e:
            print(f"Error crawling for date {date_str}: {e}")
            if retry < MAX_RETRIES:
                print(f"Retrying ({retry + 1}/{MAX_RETRIES})...")
                time.sleep(DELAY_BETWEEN_REQUESTS * 2)
                return self.crawl_for_date(date_str, level, retry + 1)
            return None

    def save_to_csv(self, data: List[Dict[str, str]], date_str: str):
        """
        Save data to separate CSV file for each month.

        Args:
            data: List of dictionaries to save
            date_str: Date string for the data (dd/MM/yyyy)
        """
        if not data:
            print("No data to save")
            return

        # Convert date string to filename
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        date_filename = date_obj.strftime("%Y_%m")  # e.g., "2022_01"
        effective_date = date_obj.strftime("%Y-%m-%d")  # e.g., "2022-01-01"

        # Add effective_date to each row
        for row in data:
            row['effective_date'] = effective_date

        # Output file: separate file per month
        output_file = self.output_dir / f"admin_divisions_{date_filename}.csv"

        if data:
            # Get all fieldnames from data
            all_fieldnames = set()
            for record in data:
                all_fieldnames.update(record.keys())

            # Sort fieldnames: effective_date first, then others alphabetically
            all_fieldnames.discard('effective_date')
            fieldnames = ['effective_date'] + sorted(list(all_fieldnames))

            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            print(f"Saved {len(data)} rows to {output_file}")


def merge_all_csv_files(output_dir: Path = OUTPUT_DIR) -> Path:
    """
    Merge all monthly CSV files into a single deduplicated file.

    Deduplication logic:
    - Key: column_1 (ward name) + column_5 (district name) + column_7 (province name)
    - Keep the record with the latest effective_date for each unique location

    Args:
        output_dir: Directory containing monthly CSV files

    Returns:
        Path to the merged output file
    """
    import pandas as pd

    output_dir = Path(output_dir)
    all_files = sorted(output_dir.glob("admin_divisions_????_??.csv"))

    if not all_files:
        print("No CSV files found to merge")
        return None

    print(f"\nMerging {len(all_files)} CSV files...")

    # Read all CSV files
    dfs = []
    for i, file in enumerate(all_files, 1):
        try:
            if i % 10 == 0 or i == 1:
                print(f"Reading file {i}/{len(all_files)}: {file.name}")
            df = pd.read_csv(file, encoding='utf-8-sig')
            dfs.append(df)
        except Exception as e:
            print(f"Warning: Could not read {file.name}: {e}")

    if not dfs:
        print("No data to merge")
        return None

    # Concatenate all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    total_records_before = len(combined_df)
    print(f"Total records before deduplication: {total_records_before:,}")

    # Create composite key for deduplication
    combined_df['_dedup_key'] = (
        combined_df['column_1'].fillna('').astype(str) + '|' +
        combined_df['column_5'].fillna('').astype(str) + '|' +
        combined_df['column_7'].fillna('').astype(str)
    )

    # Convert effective_date to datetime for proper comparison
    combined_df['effective_date'] = pd.to_datetime(combined_df['effective_date'])

    # Sort by dedup_key and effective_date (descending) to get latest first
    combined_df = combined_df.sort_values(
        by=['_dedup_key', 'effective_date'],
        ascending=[True, False]
    )

    # Keep only the first (latest) record for each unique location
    deduplicated_df = combined_df.drop_duplicates(subset='_dedup_key', keep='first')

    # Drop the temporary dedup key column
    deduplicated_df = deduplicated_df.drop(columns=['_dedup_key'])

    # Convert effective_date back to string format
    deduplicated_df['effective_date'] = deduplicated_df['effective_date'].dt.strftime('%Y-%m-%d')

    # Sort by province, district, ward for better organization
    deduplicated_df = deduplicated_df.sort_values(
        by=['column_7', 'column_5', 'column_1']
    )

    total_records_after = len(deduplicated_df)
    duplicates_removed = total_records_before - total_records_after

    print(f"Total records after deduplication: {total_records_after:,}")
    print(f"Duplicates removed: {duplicates_removed:,} ({duplicates_removed/total_records_before*100:.1f}%)")

    # Save to output file
    output_file = output_dir / "admin_divisions_all.csv"
    deduplicated_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"✓ Saved merged data to {output_file}")

    return output_file


def generate_monthly_dates(start_date: str, end_date: Optional[str] = None) -> List[str]:
    """
    Generate list of first day of each month between start and end dates

    Args:
        start_date: Start date in "dd/MM/yyyy" format (e.g., "01/01/2022")
        end_date: End date in "dd/MM/yyyy" format (default: today)

    Returns:
        List of date strings in "dd/MM/yyyy" format
    """
    start = datetime.strptime(start_date, "%d/%m/%Y")
    end = datetime.strptime(end_date, "%d/%m/%Y") if end_date else datetime.now()

    dates = []
    current = start

    while current <= end:
        dates.append(current.strftime("%d/%m/%Y"))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return dates


def main():
    parser = argparse.ArgumentParser(
        description="Crawl Vietnamese Administrative Divisions from GSO website"
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date in dd/MM/yyyy format (default: auto-detect from existing data or 01/01/2022)"
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date in dd/MM/yyyy format (default: today)"
    )

    args = parser.parse_args()

    # Determine start date
    if args.start_date:
        start_date = args.start_date
    else:
        # Auto-detect from existing CSV files (find latest month)
        if OUTPUT_DIR.exists():
            csv_files = sorted(OUTPUT_DIR.glob("admin_divisions_*.csv"))
            if csv_files:
                # Get latest file
                latest_file = csv_files[-1]
                # Extract date from filename: admin_divisions_2022_01.csv -> 2022_01
                filename = latest_file.stem  # admin_divisions_2022_01
                date_part = filename.replace("admin_divisions_", "")  # 2022_01
                try:
                    year, month = date_part.split("_")
                    latest_dt = datetime(int(year), int(month), 1)
                    # Move to next month
                    if latest_dt.month == 12:
                        next_dt = latest_dt.replace(year=latest_dt.year + 1, month=1)
                    else:
                        next_dt = latest_dt.replace(month=latest_dt.month + 1)
                    start_date = next_dt.strftime("%d/%m/%Y")
                    print(f"Auto-detected start date: {start_date} (next month after {latest_file.name})")
                except Exception as e:
                    print(f"Error parsing latest file date: {e}")
                    start_date = "01/01/2022"
                    print(f"Using default start date: {start_date}")
            else:
                start_date = "01/01/2022"
                print(f"No existing CSV files, using default start date: {start_date}")
        else:
            start_date = "01/01/2022"
            print(f"Output directory doesn't exist, using default start date: {start_date}")

    # Generate dates to crawl
    dates = generate_monthly_dates(start_date, args.end_date)

    print("=" * 80)
    print("VIETNAMESE ADMINISTRATIVE DIVISION CRAWLER")
    print("=" * 80)
    print(f"Target URL: {BASE_URL}")
    print(f"Admin Level: Xã (Ward - most detailed)")
    print(f"Date range: {dates[0] if dates else 'N/A'} → {dates[-1] if dates else 'N/A'}")
    print(f"Total months to crawl: {len(dates)}")
    print(f"Output: {OUTPUT_DIR / 'admin_divisions_all.csv'}")
    print(f"Mode: Combined with deduplication (keep latest effective_date)")
    print(f"Browser: Headless (no GUI)")
    print("=" * 80)

    # Start crawling (always headless, always Xã level)
    with AdminDivisionCrawler(headless=True, output_dir=OUTPUT_DIR) as crawler:
        success_count = 0
        fail_count = 0

        for i, date_str in enumerate(dates, 1):
            print(f"\n[{i}/{len(dates)}] Crawling data for {date_str}...")

            # Check if file already exists
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            date_filename = date_obj.strftime("%Y_%m")
            output_file = OUTPUT_DIR / f"admin_divisions_{date_filename}.csv"

            if output_file.exists():
                print(f"✓ Skipping {date_filename} (file already exists)")
                success_count += 1
                continue

            data = crawler.crawl_for_date(date_str, level="Xã")

            if data:
                crawler.save_to_csv(data, date_str)
                success_count += 1
            else:
                print(f"Failed to crawl data for {date_str}")
                fail_count += 1

            # Delay between requests
            if i < len(dates):
                print(f"Waiting {DELAY_BETWEEN_REQUESTS} seconds before next request...")
                time.sleep(DELAY_BETWEEN_REQUESTS)

        print("\n" + "=" * 80)
        print("CRAWLING COMPLETED")
        print("=" * 80)
        print(f"Success: {success_count}/{len(dates)}")
        print(f"Failed: {fail_count}/{len(dates)}")
        print("=" * 80)

        # Merge all CSV files into one deduplicated file
        print("\n" + "=" * 80)
        print("MERGING DATA")
        print("=" * 80)
        merged_file = merge_all_csv_files(OUTPUT_DIR)
        if merged_file:
            print("=" * 80)
            print(f"✓ Final output: {merged_file}")
            print("=" * 80)
        else:
            print("Failed to merge CSV files")
            print("=" * 80)


if __name__ == "__main__":
    main()
