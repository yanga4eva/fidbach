import time
import logging
import urllib.parse
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.core.db import add_job_to_queue

logger = logging.getLogger(__name__)

class CompanyCrawler:
    """
    Phase 7 Autonomous Universal Scraper:
    Navigates to a company homepage, finds the Careers portal, identifies the ATS, 
    and queues job links for the main ReAct worker.
    """
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def ats_fingerprint(self, url: str) -> str:
        """Analyzes the URL to determine the ATS platform."""
        url_lower = url.lower()
        if 'workday' in url_lower or 'myworkdayjobs' in url_lower:
            return 'Workday'
        elif 'greenhouse.io' in url_lower:
            return 'Greenhouse'
        elif 'lever.co' in url_lower:
            return 'Lever'
        elif 'icims.com' in url_lower:
            return 'iCIMS'
        elif 'ashbyhq' in url_lower:
            return 'Ashby'
        return 'Unknown ATS'

    def _find_careers_link_on_page(self, domain: str) -> str | None:
        """Scans the current page DOM for common Career page links."""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        target_texts = ['careers', 'jobs', 'join us', 'work with us', 'openings']
        
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).lower()
            if any(t in text for t in target_texts):
                href = a['href']
                if href.startswith('/'):
                    return f"https://www.{domain}{href}"
                elif 'http' in href:
                    return href
        return None

    def find_and_queue_jobs(self, company_domain: str, target_keywords: str) -> int:
        """
        1. Navigates to the homepage or Uses Google to find the careers page.
        2. Deep Link Detection: Fingerprints the ATS.
        3. Attempts to find links matching the target keywords.
        4. Queues them in the DB.
        """
        logger.info(f"Initiating autonomous crawl for '{company_domain}' searching for '{target_keywords}'")
        jobs_added = 0
        clean_domain = company_domain.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        careers_url = None
        
        try:
            # Step 1a: Direct Homepage Discovery
            logger.info(f"Attempting direct homepage discovery on https://www.{clean_domain}")
            self.driver.get(f"https://www.{clean_domain}")
            time.sleep(4)
            careers_url = self._find_careers_link_on_page(clean_domain)
            
            # Step 1b: Fallback to Google Dorking
            if not careers_url:
                logger.info("Direct link not found in DOM. Falling back to Google Search.")
                search_query = f"site:{clean_domain} careers OR jobs"
                encoded_query = urllib.parse.quote_plus(search_query)
                self.driver.get(f"https://www.google.com/search?q={encoded_query}")
                time.sleep(3)
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                search_results = soup.find_all('a')
                
                for a in search_results:
                    href = a.get('href', '')
                    if href.startswith('http') and clean_domain in href and 'google.com' not in href:
                        careers_url = href
                        break
                        
            if not careers_url:
                logger.warning(f"Could not locate the Careers portal for {company_domain}")
                return 0
                
            # Step 2: Navigate and ATS Fingerprint
            platform = self.ats_fingerprint(careers_url)
            logger.info(f"Located Careers Portal: {careers_url}. Detected Platform: {platform}")
            
            self.driver.get(careers_url)
            time.sleep(5) # Hydration time
            
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
            # Step 3: Parse the custom job feed
            careers_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            all_links = careers_soup.find_all('a')
            
            keyword_list = [k.strip().lower() for k in target_keywords.split(',')]
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True).lower()
                
                if href and len(text) > 5 and any(kw in text for kw in keyword_list):
                    if href.startswith('/'):
                        base_url = "/".join(careers_url.split('/')[:3])
                        full_url = base_url + href
                    else:
                        full_url = href
                        
                    # Queue it up. The platform fingerprint is appended to the company name for agent context.
                    company_with_context = f"{company_domain} [{platform}]"
                    if add_job_to_queue(full_url, link.get_text(strip=True), company_with_context):
                        logger.info(f"Autonomously queued job: {full_url}")
                        jobs_added += 1
                        if jobs_added >= 15:
                            break
                            
            return jobs_added

        except Exception as e:
            logger.error(f"Critical error during autonomous crawl of {company_domain}: {e}")
            return jobs_added
