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

class JobScraper:
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def scrape_linkedin_jobs(self, keywords: str, location: str, max_jobs: int = 15) -> int:
        """
        Scrapes job URLs from LinkedIn's public job board without logging in.
        Returns the number of jobs successfully added to the queue.
        """
        logger.info(f"Starting LinkedIn scrape for '{keywords}' in '{location}'")
        jobs_added = 0
        
        try:
            # Build the public search URL
            query = urllib.parse.quote_plus(keywords)
            loc = urllib.parse.quote_plus(location)
            url = f"https://www.linkedin.com/jobs/search?keywords={query}&location={loc}&f_TPR=r86400" # Past 24 hours
            
            self.driver.get(url)
            time.sleep(5) # Wait for initial load
            
            # Scroll to load dynamic content
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find all job cards
            job_cards = soup.find_all('div', class_='base-card')
            
            for card in job_cards:
                if jobs_added >= max_jobs:
                    break
                    
                title_elem = card.find('h3', class_='base-search-card__title')
                company_elem = card.find('h4', class_='base-search-card__subtitle')
                link_elem = card.find('a', class_='base-card__full-link')
                
                if title_elem and company_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    company = company_elem.get_text(strip=True)
                    # Clean tracking parameters from URL
                    job_url = link_elem['href'].split('?')[0]
                    
                    if add_job_to_queue(job_url, title, company):
                        logger.info(f"Queued: {title} at {company}")
                        jobs_added += 1
                        
            return jobs_added
            
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {e}")
            return jobs_added

    def scrape_google_jobs(self, keywords: str, max_jobs: int = 15) -> int:
        """
        Scrapes job URLs from Google Jobs.
        """
        logger.info(f"Starting Google Jobs scrape for '{keywords}'")
        jobs_added = 0
        
        try:
            query = urllib.parse.quote_plus(f"{keywords} jobs")
            url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"
            
            self.driver.get(url)
            time.sleep(5)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Google Jobs layout changes frequently, this is a basic heuristic
            # looking for standard structural classes
            job_items = soup.find_all('li')
            
            for item in job_items:
                if jobs_added >= max_jobs:
                    break
                    
                # Very basic extraction logic for Google's obfuscated DOM
                link_elem = item.find('a')
                if link_elem and 'href' in link_elem.attrs:
                    job_url = link_elem['href']
                    if 'google.com/search' not in job_url and job_url.startswith('http'):
                        if add_job_to_queue(job_url, f"Google Search Result {jobs_added+1}", "Unknown Company"):
                            jobs_added += 1
                            
            return jobs_added
            
        except Exception as e:
            logger.error(f"Error scraping Google Jobs: {e}")
            return jobs_added
