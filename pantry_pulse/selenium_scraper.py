import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Products can also be configured via SCRAPE_PRODUCTS (pipe-separated)
PRODUCTS = os.environ.get('SCRAPE_PRODUCTS')
if PRODUCTS:
    PRODUCTS = [p.strip() for p in PRODUCTS.split('|') if p.strip()]
else:
    # Comprehensive grocery list (~300+ everyday items across all categories)
    PRODUCTS = [
        # Dairy & Milk (18 items)
        'Mlieko 2.5% 1l', 'Mlieko 3.5% 1l', 'Mlieko bez laktózy 1l',
        'Jogurt prírodný 150g', 'Jogurt ovocný 150g', 'Grécky jogurt 150g',
        'Kefír 500ml', 'Tvaroh 250g', 'Smotana 200ml 18%', 'Smotana 200ml 36%',
        'Maslo tradičné 250g', 'Margarin 250g', 'Syr Parenice 1kg', 'Syr Oravský 1kg',
        'Syr Parenice 250g', 'Syr Bryndzový 200g', 'Syr Liptovský 200g', 'Syr Eidam 200g',
        
        # Eggs (3 items)
        'Vajcia S 10ks', 'Vajcia L 10ks', 'Vajcia XL 10ks',
        
        # Fresh Meat & Fish (19 items)
        'Kuracie prsia 1kg', 'Kuracie stehná 1kg', 'Mleté kuracie 500g',
        'Hovädzie steak 500g', 'Hovädzie guláš 500g', 'Mleté hovädzie 500g',
        'Bravčové stehno 1kg', 'Mleté bravčové 500g', 'Bravčová chrbtica 1kg',
        'Morská ryba filet 400g', 'Losos filet 400g', 'Tuna konzervovaná 185g',
        'Klobása domáca 400g', 'Špikovaná slanina 200g', 'Sliepkové prsia 500g',
        'Jahňacia mäso 500g', 'Bravčová pečeň 500g', 'Kuracie miesko 1kg', 'Ryba pstruh 400g',
        
        # Bakery & Bread (25 items)
        'Chlieb klasický 500g', 'Chlieb žitný 500g', 'Chlieb bez lepku 500g',
        'Chlieb bielý 500g', 'Chlieb čierny 500g', 'Valcový chlieb 500g',
        'Kváskový chlieb 500g', 'Grahamový chlieb 400g', 'Rozuk 100g',
        'Rožky 80g', 'Croissant vanila 40g', 'Croissant čokoláda 40g', 'Donut 50g',
        'Syrečky chlieb 150g', 'Žemľa syrová 1ks', 'Obloženka koprivnica 1ks',
        'Obloženka salát 1ks', 'Chlieb s orechovcom 500g', 'Syrečky chlieb 500g',
        'Kváskový chlieb kváska 300g', 'Bageta 300g', 'Baguette 300g', 'Mini žemle 4ks',
        'Ciabatta 250g', 'Focaccia 300g',
        
        # Pasta & Starches (30 items)
        'Cestoviny 500g', 'Cestoviny špagety 500g', 'Cestoviny penne 500g',
        'Cestoviny fusilli 500g', 'Cestoviny farfalle 500g', 'Cestoviny lasagne 500g',
        'Ryža 1kg', 'Ryža basmati 1kg', 'Ryža jazmínová 1kg', 'Ryža parboiled 1kg',
        'Kuskus 500g', 'Quinoa 500g', 'Bulgur 500g', 'Jačmeň 1kg', 'Proso 1kg',
        'Šošovica 1kg', 'Fazuľa 1kg', 'Hrach 1kg', 'Cizrna 1kg', 'Šošovica červená 500g',
        'Múka pšeničná 1kg', 'Múka ražná 1kg', 'Múka kukuričná 1kg', 'Múka špaldová 1kg',
        'Múka kokosová 500g', 'Múka mandľová 500g', 'Krupica 1kg', 'Ovsené vločky 500g',
        'Pohánka 500g', 'Amarant 500g',
        
        # Fruits (15 items)
        'Jablká 1kg', 'Hrušky 1kg', 'Broskyne 500g', 'Marhule 500g', 'Slivky 1kg',
        'Čerešne 500g', 'Višne 500g', 'Maliny 250g', 'Jahody 500g', 'Borievky 250g',
        'Banány 1kg', 'Pomaranče 1kg', 'Mandarínky 1kg', 'Citróň 1ks', 'Ananás 1ks',
        'Jablká červené 1kg', 'Jablká zelené 1kg', 'Hrozno biele 1kg', 'Hrozno červené 1kg',
        'Kiwi 500g', 'Mango 1ks', 'Avokádo 1ks', 'Granátové jablko 1ks', 'Papája 1ks',
        'Dragon fruit 1ks',
        
        # Vegetables (20 items)
        'Zemiaky 1kg', 'Cibuľa 1kg', 'Cesnak 200g', 'Mrkva 1kg', 'Petržlen 1ks',
        'Zeler 1ks', 'Paradajky 1kg', 'Uhorky 1kg', 'Paprika 1kg', 'Baklažán 1ks',
        'Špenát 300g', 'Šalát 1ks', 'Kaleráb 1ks', 'Karfiol 1ks', 'Brokolica 500g',
        'Kapusta 1ks', 'Kukurica 1ks', 'Špargľa 500g', 'Reďkovka 500g', 'Rettich 1ks',
        'Tekvica 1kg', 'Cuketa 1kg', 'Fazuľové struky 500g', 'Hrachový struky 500g',
        'Špenátový list 300g',
        
        # Oils & Fats (10 items)
        'Olej slnečnicový 1l', 'Olej olivový 500ml', 'Olej kokosový 500ml', 'Maslo 250g',
        'Margarín 250g', 'Masť 200g', 'Lard 200g', 'Ghee 200g', 'Olej avokádový 250ml',
        'Olej ľanový 250ml',
        
        # Spices & Seasonings (15 items)
        'Soľ 1kg', 'Cukor 1kg', 'Múka 1kg', 'Kypriaci prášok 200g', 'Soda bikarbóna 200g',
        'Vanilkový cukor 200g', 'Škorica 50g', 'Koriander 50g', 'Kmín 50g', 'Majorán 50g',
        'Tymián 50g', 'Rozmarín 50g', 'Bazalka 50g', 'Oregano 50g', 'Paprika sladká 100g',
        'Chilli prášok 50g', 'Kurkuma 50g', 'Zázvor 50g', 'Šafrán 1g', 'Vanilka 1ks',
        
        # Canned & Preserved (15 items)
        'Paradajková omáčka 500g', 'Kečup 500g', 'Horčica 200g', 'Majonéza 400g', 'Ocot 500ml',
        'Sojová omáčka 250ml', 'Worcester omáčka 250ml', 'Teriyaki omáčka 250ml', 'BBQ omáčka 500g',
        'Česneková pasta 200g', 'Zázvorová pasta 200g', 'Wasabi pasta 50g', 'Harissa pasta 200g',
        'Pesto bazalkové 200g', 'Pesto česnekové 200g',
        
        # Beverages (10 items)
        'Voda minerálna 1.5l', 'Voda pramenitá 1.5l', 'Džús jablkový 1l', 'Džús pomarančový 1l',
        'Džús višňový 1l', 'Čaj čierny 100g', 'Čaj zelený 100g', 'Káva mletá 250g', 'Káva instant 200g',
        'Kakao 200g',
        
        # Sweets & Snacks (20 items)
        'Čokoláda mliečna 100g', 'Čokoláda horká 100g', 'Bonbóny 200g', 'Žuvačky 100g', 'Cukríky 200g',
        'Sušené ovocie 200g', 'Orechy 200g', 'Semienka 200g', 'Popcorn 100g', 'Čipsy 150g',
        'Krekry 200g', 'Sušienky 300g', 'Koláče 500g', 'Torty 1kg', 'Zmrzlina 500ml',
        'Med 500g', 'Džem 400g', 'Nutella 400g', 'Marmeláda 400g', 'Sirup 500ml',
        
        # Frozen Foods (10 items)
        'Zmrazené jahody 500g', 'Zmrazené maliny 500g', 'Zmrazené brokolica 500g', 'Zmrazené karfiol 500g',
        'Zmrazené ryža 1kg', 'Zmrazené cestoviny 500g', 'Zmrazené pizza 400g', 'Zmrazené hranolky 1kg',
        'Zmrazené ryba 400g', 'Zmrazené mäso 500g',
        
        # Household & Cleaning (10 items)
        'Mýdlo 100g', 'Šampón 250ml', 'Sprchový gél 250ml', 'Zubná pasta 100ml', 'Zubná kefka 1ks',
        'Toaletný papier 8ks', 'Papierové utierky 100ks', 'Pracie prášok 3kg', 'Aviváž 1.5l', 'Čistič 500ml',
        
        # Personal Care (10 items)
        'Parfum 50ml', 'Deodorant 150ml', 'Krém na ruky 100ml', 'Krém na tvár 50ml', 'Šampón na vlasy 250ml',
        'Kondicionér 250ml', 'Maskara 10ml', 'Rúž 5g', 'Puder 20g', 'Lak na nechty 10ml',
        
        # Baby & Child (5 items)
        'Plienky 50ks', 'Mlieko pre deti 800g', 'Kaša pre deti 200g', 'Hračky 1ks', 'Oblečenie pre deti 1ks',
        
        # Pet Food (5 items)
        'Krmivo pre psy 5kg', 'Krmivo pre mačky 5kg', 'Krmivo pre vtáky 1kg', 'Krmivo pre ryby 100g', 'Krmivo pre hlodavce 1kg',
        
        # Other (5 items)
        'Baterky 4ks', 'Žiarovky 5ks', 'Náradie 1ks', 'Knihy 1ks', 'Hračky 1ks',
    ]

class SeleniumScraper:
    def __init__(self):
        self.stores = {
            'Tesco': 'https://www.tesco.sk',
            'Kaufland': 'https://www.kaufland.sk',
            'Billa': 'https://www.billa.sk',
            'Lidl': 'https://www.lidl.sk',
            'Penny': 'https://www.penny.sk',
            'Albert': 'https://www.alberts.sk',
            'Coop': 'https://www.coopobchod.sk',
            'OKAY': 'https://www.okay.sk',
            'Eurospar': 'https://www.eurospar.sk',
        }
        self.headless = os.environ.get('SELENIUM_HEADLESS', 'True').lower() == 'true'

    def scrape_all(self, products_to_scrape=None):
        """Scrape all stores in parallel for speed
        
        Args:
            products_to_scrape: Optional list of product names to scrape. If None, scrapes all PRODUCTS
        """
        if products_to_scrape is None:
            products_to_scrape = PRODUCTS
            
        all_prices = {}

        def scrape_store_task(store_name, base_url):
            driver = self.get_driver()
            try:
                return store_name, self.scrape_store(driver, store_name, base_url, products_to_scrape)
            finally:
                driver.quit()

        # Use thread pool to scrape stores in parallel (faster than sequential)
        max_workers = min(len(self.stores), 4)  # Max 4 concurrent browsers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(scrape_store_task, name, url): name
                for name, url in self.stores.items()
            }
            for future in as_completed(futures):
                try:
                    store_name, prices = future.result()
                    all_prices[store_name] = prices
                except Exception as e:
                    logger.error(f"Scrape task failed: {e}")

        return all_prices

    def get_driver(self):
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return webdriver.Chrome(service=service, options=options)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _safe_get(self, driver, url):
        driver.get(url)
        # Wait for page to load (reduced timeout for speed)
        WebDriverWait(driver, 5).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    def _scrape_product(self, driver, store_name, product, base_url):
        """Scrape a single product from a store"""
        try:
            query = product.lower().replace(' ', '+')
            url = f"{base_url}/search?q={query}" if 'lidl' not in base_url.lower() else f"{base_url}/c/potraviny?q={query}"
            logger.info(f"Scraping {store_name}: {product}")
            self._safe_get(driver, url)
            price = self.extract_price(driver)
            return product, price
        except Exception as e:
            logger.error(f"{store_name} {product}: {e}")
            return product, None

    def scrape_store(self, driver, store_name, base_url, products_to_scrape=None):
        prices = {}

        if products_to_scrape is None:
            products_to_scrape = PRODUCTS

        # Scrape products sequentially to avoid browser overload
        # (Using multiple threads with one driver per thread in scrape_all)
        for product in products_to_scrape:
            product_name, price = self._scrape_product(driver, store_name, product, base_url)
            if price is not None:
                prices[product_name] = price

        logger.info(f"{store_name} scraped: {len(prices)}/{len(products_to_scrape)} products found")
        return prices

    def extract_price(self, driver):
        price_selectors = [
            '[class*="price"]', '[class*="Price"]', '[data-price]', '.price-current', '.product-price',
            '[class*="eur"]', '.amount', '.Price-amount__value', '.price__value'
        ]
        for selector in price_selectors:
            try:
                element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                text = element.text.strip()
                match = re.search(r'(\d+[, ]\d{2})\s*€?', text)
                if match:
                    price_str = match.group(1).replace(' ', '').replace(',', '.')
                    price = float(price_str)
                    if 0.01 <= price <= 50:  # Reasonable price range for groceries
                        logger.info(f"Found price: {price}€")
                        return price
            except:
                continue
        
        # Fallback: search entire page source for price patterns
        try:
            page_source = driver.page_source
            # Look for prices like 1.99€ or 1,99 €
            matches = re.findall(r'\b(\d+[\.,]\d{2})\s*€?\b', page_source)
            if matches:
                # Take the first reasonable price (assume it's the main product price)
                for match in matches:
                    price = float(match.replace(',', '.'))
                    if 0.01 <= price <= 50:  # Reasonable price range
                        logger.info(f"Found price in page source: {price}€")
                        return price
        except Exception as e:
            logger.error(f"Error extracting price from page source: {e}")
        
        return None

if __name__ == '__main__':
    from app import app, db
    with app.app_context():
        db.create_all()
        scraper = SeleniumScraper()
        prices = scraper.scrape_all()
        from app import _save_scraped_data
        _save_scraped_data(prices, scraper)
        logger.info(f"Saved {sum(len(v) for v in prices.values())} prices")