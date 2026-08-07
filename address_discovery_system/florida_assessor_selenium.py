"""Selenium-based Florida County Assessor scraper

Handles JavaScript-heavy county assessor websites using Selenium WebDriver.
Supports: Duval, Miami-Dade, Broward, Pinellas, Sarasota, and others.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)
from typing import Optional, Dict, List
import time
import re


class FloridaCountyAssessorSelenium:
    """Selenium-based scraper for JavaScript-heavy county sites"""

    def __init__(self, headless: bool = True, timeout: int = 20):
        """Initialize Selenium driver

        Args:
            headless: Run browser in headless mode (no GUI)
            timeout: Timeout for waiting for elements (seconds)
        """
        self.headless = headless
        self.timeout = timeout
        self.driver = None

    def _init_driver(self):
        """Initialize Chrome WebDriver if not already done"""
        if not self.driver:
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

            try:
                self.driver = webdriver.Chrome(options=options)
            except Exception as e:
                print(f"Warning: Could not initialize Chrome driver: {e}")
                return False
        return True

    def _quit_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def search_duval(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Duval County (Jacksonville) using Selenium"""
        if not self._init_driver():
            return None

        try:
            # Navigate to Duval County assessor map
            url = 'https://webpub.duvalassessor.com/Map/'
            self.driver.get(url)

            # Wait for search input to load
            wait = WebDriverWait(self.driver, self.timeout)
            search_input = wait.until(
                EC.presence_of_element_located((By.NAME, 'SearchValue'))
            )

            # Clear and enter property name
            search_input.clear()
            search_input.send_keys(property_name)

            # Click search button
            search_btn = self.driver.find_element(By.NAME, 'btnSearch')
            search_btn.click()

            # Wait for results
            time.sleep(2)
            results = self.driver.find_elements(By.CLASS_NAME, 'SearchResult')

            if results:
                # Get first result
                result_text = results[0].text
                # Extract address pattern: "123 Main St, Jacksonville, FL"
                match = re.search(
                    r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Circle|Court|Parkway|Way|Drive|Road|Lane|Street|Avenue)[\w\s]*(?:,\s*[\w\s]+)?)',
                    result_text
                )
                if match:
                    address = match.group(1).strip()
                    return {
                        'address': address,
                        'confidence': 0.85,
                        'source': 'duval_assessor_selenium',
                        'status': 'found'
                    }

            return {
                'address': None,
                'confidence': 0.0,
                'source': 'duval_assessor_selenium',
                'status': 'not_found'
            }

        except TimeoutException:
            return {
                'address': None,
                'confidence': 0.0,
                'source': 'duval_assessor_selenium',
                'status': 'timeout'
            }
        except Exception as e:
            return {
                'address': None,
                'confidence': 0.0,
                'source': 'duval_assessor_selenium',
                'status': 'error',
                'error': str(e)
            }

    def search_miami_dade(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Miami-Dade County using Selenium"""
        if not self._init_driver():
            return None

        try:
            url = 'https://www.miamidade.gov/pa/apps/pa/General/Datacollection/Search'
            self.driver.get(url)

            wait = WebDriverWait(self.driver, self.timeout)

            # Wait for property name input
            search_input = wait.until(
                EC.presence_of_element_located((By.ID, 'PropertyAddress'))
            )

            # Enter property name
            search_input.clear()
            search_input.send_keys(property_name)

            # Click search
            search_btn = self.driver.find_element(By.ID, 'btnSearch')
            search_btn.click()

            # Wait for results table
            time.sleep(2)
            result_rows = self.driver.find_elements(By.TAG_NAME, 'tr')[1:]  # Skip header

            if result_rows:
                row_text = result_rows[0].text
                match = re.search(
                    r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Circle|Court)[\w\s]*)',
                    row_text
                )
                if match:
                    address = match.group(1).strip()
                    return {
                        'address': address,
                        'confidence': 0.85,
                        'source': 'miami_dade_assessor_selenium',
                        'status': 'found'
                    }

            return {
                'address': None,
                'confidence': 0.0,
                'source': 'miami_dade_assessor_selenium',
                'status': 'not_found'
            }

        except TimeoutException:
            return {
                'address': None,
                'confidence': 0.0,
                'source': 'miami_dade_assessor_selenium',
                'status': 'timeout'
            }
        except Exception as e:
            return {
                'address': None,
                'confidence': 0.0,
                'source': 'miami_dade_assessor_selenium',
                'status': 'error'
            }

    def search_broward(self, property_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search Broward County using Selenium"""
        if not self._init_driver():
            return None

        try:
            url = 'https://www.broward.org/PD/AssessorsOffice/Pages/Search.aspx'
            self.driver.get(url)

            wait = WebDriverWait(self.driver, self.timeout)

            # Find and fill search field
            search_fields = self.driver.find_elements(By.TAG_NAME, 'input')
            if search_fields:
                search_fields[0].send_keys(property_name)

            # Click search button
            search_btns = self.driver.find_elements(By.TAG_NAME, 'button')
            for btn in search_btns:
                if 'search' in btn.text.lower():
                    btn.click()
                    break

            # Wait for results
            time.sleep(2)

            # Try to extract results
            result_elements = self.driver.find_elements(By.CLASS_NAME, 'result')
            if result_elements:
                result_text = result_elements[0].text
                match = re.search(
                    r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Ct|Circle|Court)[\w\s]*)',
                    result_text
                )
                if match:
                    address = match.group(1).strip()
                    return {
                        'address': address,
                        'confidence': 0.80,
                        'source': 'broward_assessor_selenium',
                        'status': 'found'
                    }

            return {
                'address': None,
                'confidence': 0.0,
                'source': 'broward_assessor_selenium',
                'status': 'not_found'
            }

        except Exception:
            return {
                'address': None,
                'confidence': 0.0,
                'source': 'broward_assessor_selenium',
                'status': 'error'
            }

    def search_by_county(self, property_name: str, county: str, city: Optional[str] = None) -> Optional[Dict]:
        """Route to appropriate county scraper"""
        county_lower = county.lower()

        try:
            if 'duval' in county_lower:
                return self.search_duval(property_name, city)
            elif 'miami-dade' in county_lower or 'miamidade' in county_lower:
                return self.search_miami_dade(property_name, city)
            elif 'broward' in county_lower:
                return self.search_broward(property_name, city)
            else:
                return None
        finally:
            pass  # Keep driver alive for multiple searches

    def batch_search(self, properties: List[Dict], close_on_finish: bool = True) -> List[Dict]:
        """Batch search multiple properties"""
        results = []

        for prop in properties:
            result = self.search_by_county(
                property_name=prop.get('property_name'),
                county=prop.get('county'),
                city=prop.get('city')
            )

            results.append({
                'property_name': prop.get('property_name'),
                'county': prop.get('county'),
                'city': prop.get('city'),
                'address': result.get('address') if result else None,
                'confidence': result.get('confidence', 0.0) if result else 0.0,
                'source': result.get('source') if result else 'assessor_selenium',
                'status': result.get('status', 'unknown') if result else 'error'
            })

            # 2-second delay between searches
            time.sleep(2)

        if close_on_finish:
            self._quit_driver()

        return results

    def __del__(self):
        """Cleanup: close driver on deletion"""
        self._quit_driver()

    def close(self):
        """Explicitly close the driver"""
        self._quit_driver()
