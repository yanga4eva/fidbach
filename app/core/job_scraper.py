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
    Phase 6 Autonomous Universal Scraper:
    Instead of relying on structured job boards, this agent takes a raw company domain,
    finds their specific ATS (Greenhouse/Workday/etc) portal via search, navigates down 
    the funnel, and queues the raw job links.
    """
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def find_and_queue_jobs(self, company_domain: str, target_keywords: str) -> int:
        """
        1. Uses Google to find the official careers page for the given domain.
        2. Navigates to the careers page.
        3. Attempts to find links matching the target keywords.
        4. Queues them in the DB.
        """
        logger.info(f"Initiating autonomous crawl for '{company_domain}' searching for '{target_keywords}'")
        jobs_added = 0
        
        try:
            # Step 1: Find the Careers Page via Dorking
            clean_domain = company_domain.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
            search_query = f"site:{clean_domain} careers OR jobs"
            encoded_query = urllib.parse.quote_plus(search_query)
            
            self.driver.get(f"https://www.google.com/search?q={encoded_query}")
            time.sleep(3) # Wait for Google
            
            # Find the first valid search result link
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            search_results = soup.find_all('a')
            
            careers_url = None
            for a in search_results:
                href = a.get('href', '')
                # Filter out Google's own links and look for the target domain
                if href.startswith('http') and clean_domain in href and 'google.com' not in href:
                    careers_url = href
                    break
                    
            if not careers_url:
                logger.warning(f"Could not automatically locate the Careers portal for {company_domain}")
                return 0
                
            logger.info(f"Located Careers Portal: {careers_url}. Navigating...")
            
            # Step 2: Navigate to the actual ATS/Careers page
            self.driver.get(careers_url)
            time.sleep(5) # Give heavy client-side React apps time to hydrate
            
            # Scroll to trigger lazy loading
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
                
                # Highly basic heuristic for identifying a job listing link
                if href and len(text) > 5 and any(kw in text for kw in keyword_list):
                    
                    # Normalize relative URLs
                    if href.startswith('/'):
                        base_url = "/".join(careers_url.split('/')[:3]) # e.g. https://jobs.netflix.com
                        full_url = base_url + href
                    else:
                        full_url = href
                        
                    # Queue it up
                    if add_job_to_queue(full_url, link.get_text(strip=True), company_domain):
                        logger.info(f"Autonomously queued job: {full_url}")
                        jobs_added += 1
                        if jobs_added >= 15: # Safety limit per company
                            break
                            
            return jobs_added

        except Exception as e:
            logger.error(f"Critical error during autonomous crawl of {company_domain}: {e}")
            return jobs_added
