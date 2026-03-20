# Pantry Pulse Scraper Fix TODO
Status: [In Progress - Step 1/6]

## Steps from Plan
### 1. **Improve selenium_scraper.py** [DONE - retries, options, cities added]
### 2. **Update app.py** [DONE - DB clear, city save, success count]
   - Add 3x retry with backoff for scrape_store.
   - Enhance Chrome options: non-headless toggle, DNS/network flags (--disable-dev-shm-usage already, add --disable-web-security --disable-features=TranslateUI --no-proxy-server, update user-agent).
   - Add store_cities dict, pass city to scrape.
   - Filter None prices, log DNS errors specifically.
   - Test URL access outside Selenium (logger.info(url)).

### 2. **Update app.py** [TODO]
   - In /scrape: Before insert, delete old PriceEntry for scraped stores/products.
   - Set store.city = cities.get(store_name, 'Bratislava').
   - Commit only if some prices succeeded.

### 3. **Update config.py** [TODO]
   - Optional: PROXY_URL = os.environ.get('HTTP_PROXY')

### 4. **Clear Stale DB** [Manual/Execute]
   - sqlite3 instance/pantry_pulse.db "DELETE FROM price_entry;"
   - sqlite3 ... "DELETE FROM store WHERE city IS NULL;" or update cities.

### 5. **Test** [TODO]
   - execute `python run.py`
   - http://127.0.0.1:5000 -> scrape, check logs/no DNS error, DB updates.
   - Query DB stores/products/prices.

### 6. **Debug Network** [If fails]
   - Test ping potraviny.tesco.sk
   - Run non-headless.
   - Update ChromeDriver manual.

Next step: [Edit selenium_scraper.py]
