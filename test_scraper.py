import urllib.parse
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import time
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

def test_search(domain):
    options = uc.ChromeOptions()
    options.add_argument(f"--display={os.environ.get('DISPLAY', ':99')}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    
    driver = uc.Chrome(options=options, version_main=145)
    
    search_query = f"{domain} careers"
    encoded_query = urllib.parse.quote_plus(search_query)
    url = f"https://www.google.com/search?q={encoded_query}"
    
    print(f"Searching: {url}")
    driver.get(url)
    time.sleep(3)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    clean_domain = domain.replace("www.", "")
    company_name = clean_domain.split('.')[0]
    
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if href.startswith('/url?q='):
            href = href.split('/url?q=')[1].split('&')[0]
            href = urllib.parse.unquote(href)
            
        if href.startswith('http') and 'google.com' not in href:
            print(f"LINK: {href}")
                
    driver.quit()

test_search("cvs.com")
print("---")
test_search("mcafee.com")
