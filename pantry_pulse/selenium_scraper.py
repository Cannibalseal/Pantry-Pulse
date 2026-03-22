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
        # Dairy & Milk (45 items) - Expanded with more variants
        'Mlieko plnotučná 3.5% 1l', 'Mlieko polotučná 1.5% 1l', 'Mlieko nízkotučná 0.5% 1l',
        'Mlieko 2.5% 1l', 'Mlieko 3.5% 1l', 'Mlieko bez laktózy 1l',
        'Mlieko bez laktózy plnotučná 1l', 'Mlieko bez laktózy nízkotučná 1l',
        'Mlieko ovocné jablko 1l', 'Mlieko ovocné čokoláda 1l', 'Mlieko ovocné vanilka 1l',
        'Jogurt prírodný 150g', 'Jogurt ovocný 150g', 'Grécky jogurt 150g',
        'Jogurt nízkotučný 150g', 'Jogurt biely 150g', 'Jogurt vanilkový 150g',
        'Jogurt čokoládový 150g', 'Jogurt jahodový 150g', 'Jogurt banánový 150g',
        'Kefír 500ml', 'Kefír nízkotučný 500ml', 'Tvaroh 250g', 'Tvaroh nízkotučný 250g',
        'Smotana 200ml 18%', 'Smotana 200ml 36%', 'Smotana na šľahanie 200ml',
        'Maslo tradičné 250g', 'Maslo nízkotučné 250g', 'Margarin 250g', 'Margarin ľahký 250g',
        'Syr Parenice 1kg', 'Syr Oravský 1kg', 'Syr Eidam 1kg', 'Syr Gouda 1kg',
        'Syr Parenice 250g', 'Syr Bryndzový 200g', 'Syr Liptovský 200g', 'Syr Eidam 200g',
        'Syr Mozzarella 200g', 'Syr Feta 200g', 'Syr Cottage 250g', 'Syr Ricotta 250g',
        'Biely jogurt 150g', 'Vanilkový jogurt 150g', 'Šľahačka 200ml', 'Šľahačka na šľahanie 500ml',
        'Kyslá smotana 200g', 'Kyslá smotana ľahká 200g', 'Mliečna zmrzlina vanilka 500ml',
        'Mliečna zmrzlina čokoláda 500ml', 'Mliečna zmrzlina jahoda 500ml', 'Tvarohový dezert 150g',
        
        # Eggs (8 items)
        'Vajcia S 10ks', 'Vajcia L 10ks', 'Vajcia XL 10ks', 'Vajcia M 10ks',
        'Vajcia bio 6ks', 'Vajcia voľný chov 6ks', 'Vajcia bez klietok 6ks', 'Vajcia čerstvé 12ks',
        
        # Fresh Meat & Fish (35 items)
        'Kuracie prsia 1kg', 'Kuracie stehná 1kg', 'Mleté kuracie 500g', 'Kuracie krídla 1kg',
        'Kuracie celé 1.5kg', 'Kuracie filet 500g', 'Hovädzie steak 500g', 'Hovädzie guláš 500g',
        'Mleté hovädzie 500g', 'Hovädzie rebrá 500g', 'Hovädzie svíčková 500g', 'Bravčové stehno 1kg',
        'Mleté bravčové 500g', 'Bravčová chrbtica 1kg', 'Bravčové kotlety 500g', 'Bravčová panenka 500g',
        'Morská ryba filet 400g', 'Losos filet 400g', 'Tuna konzervovaná 185g', 'Treska filet 400g',
        'Šťuka filet 400g', 'Zubatka filet 400g', 'Klobása domáca 400g', 'Klobása pražská 400g',
        'Klobása debrecínska 400g', 'Špikovaná slanina 200g', 'Slanina domáca 300g', 'Sliepkové prsia 500g',
        'Jahňacia mäso 500g', 'Jahňacie kotlety 500g', 'Bravčová pečeň 500g', 'Kuracie miesko 1kg',
        'Ryba pstruh 400g', 'Ryba kapor 1kg', 'Ryba zubatka 400g', 'Mäso na guláš 500g',
        
        # Bakery & Bread (40 items)
        'Chlieb klasický 500g', 'Chlieb žitný 500g', 'Chlieb bez lepku 500g', 'Chlieb bielý 500g',
        'Chlieb čierny 500g', 'Valcový chlieb 500g', 'Kváskový chlieb 500g', 'Grahamový chlieb 400g',
        'Chlieb pšeničný 500g', 'Chlieb ražný 500g', 'Chlieb špaldový 400g', 'Rozuk 100g',
        'Rožky 80g', 'Rožky maslové 80g', 'Croissant vanila 40g', 'Croissant čokoláda 40g',
        'Croissant maslový 60g', 'Donut 50g', 'Donut čokoládový 50g', 'Syrečky chlieb 150g',
        'Žemľa syrová 1ks', 'Žemľa maslová 1ks', 'Obloženka koprivnica 1ks', 'Obloženka salát 1ks',
        'Obloženka šunka 1ks', 'Chlieb s orechovcom 500g', 'Syrečky chlieb 500g', 'Kváskový chlieb kváska 300g',
        'Bageta 300g', 'Baguette 300g', 'Mini žemle 4ks', 'Ciabatta 250g', 'Focaccia 300g',
        'Chlebíčky 6ks', 'Chlebíčky maslové 6ks', 'Buchty 4ks', 'Buchty makové 4ks', 'Buchty tvarohové 4ks',
        'Koláče 500g', 'Koláče makový 500g', 'Koláče orechový 500g',
        
        # Pasta & Starches (50 items) - Expanded with more varieties
        'Cestoviny 500g', 'Cestoviny špagety 500g', 'Cestoviny penne 500g', 'Cestoviny fusilli 500g',
        'Cestoviny farfalle 500g', 'Cestoviny lasagne 500g', 'Cestoviny makaróny 500g', 'Cestoviny rezance 500g',
        'Cestoviny bez lepku 500g', 'Cestoviny celozrnné 500g', 'Ryža 1kg', 'Ryža basmati 1kg',
        'Ryža jazmínová 1kg', 'Ryža parboiled 1kg', 'Ryža čierna 500g', 'Ryža divoká 500g',
        'Kuskus 500g', 'Quinoa 500g', 'Bulgur 500g', 'Jačmeň 1kg', 'Proso 1kg', 'Šošovica 1kg',
        'Fazuľa 1kg', 'Hrach 1kg', 'Cizrna 1kg', 'Šošovica červená 500g', 'Šošovica zelená 500g',
        'Múka pšeničná hrubá 1kg', 'Múka pšeničná polohrúbka 1kg', 'Múka pšeničná jemná 1kg',
        'Múka ražná hrubá 1kg', 'Múka ražná polohrúbka 1kg', 'Múka ražná jemná 1kg',
        'Múka kukuričná 1kg', 'Múka špaldová 1kg', 'Múka kokosová 500g', 'Múka mandľová 500g',
        'Múka ryžová 500g', 'Múka pohánková 500g', 'Krupica 1kg', 'Ovsené vločky 500g',
        'Ovsené vločky instant 500g', 'Pohánka 500g', 'Amarant 500g', 'Čirok 500g',
        'Špaldové vločky 500g', 'Jačmenné vločky 500g', 'Pšeničné vločky 500g', 'Kukuričné vločky 500g',
        'Múka na lívance 500g', 'Múka na chlieb 1kg', 'Múka na pečenie 500g',
        
        # Fruits (35 items)
        'Jablká 1kg', 'Hrušky 1kg', 'Broskyne 500g', 'Marhule 500g', 'Slivky 1kg',
        'Čerešne 500g', 'Višne 500g', 'Maliny 250g', 'Jahody 500g', 'Borievky 250g',
        'Banány 1kg', 'Pomaranče 1kg', 'Mandarínky 1kg', 'Citróň 1ks', 'Ananás 1ks',
        'Jablká červené 1kg', 'Jablká zelené 1kg', 'Hrozno biele 1kg', 'Hrozno červené 1kg',
        'Kiwi 500g', 'Mango 1ks', 'Avokádo 1ks', 'Granátové jablko 1ks', 'Papája 1ks',
        'Dragon fruit 1ks', 'Limetka 1ks', 'Grapefruit 1ks', 'Nektarínky 500g', 'Brokvica 500g',
        'Ríbezle červené 250g', 'Ríbezle čierne 250g', 'Egreše 250g', 'Ostružiny 250g',
        'Durian 1ks', 'Karambola 1ks',
        
        # Vegetables (40 items)
        'Zemiaky 1kg', 'Cibuľa 1kg', 'Cesnak 200g', 'Mrkva 1kg', 'Petržlen 1ks',
        'Zeler 1ks', 'Paradajky 1kg', 'Uhorky 1kg', 'Paprika 1kg', 'Baklažán 1ks',
        'Špenát 300g', 'Šalát 1ks', 'Kaleráb 1ks', 'Karfiol 1ks', 'Brokolica 500g',
        'Kapusta 1ks', 'Kukurica 1ks', 'Špargľa 500g', 'Reďkovka 500g', 'Rettich 1ks',
        'Tekvica 1kg', 'Cuketa 1kg', 'Fazuľové struky 500g', 'Hrachový struky 500g',
        'Špenátový list 300g', 'Šalát hlávkový 1ks', 'Šalát ľadový 1ks', 'Rukola 100g',
        'Špenát baby 150g', 'Kôpor 50g', 'Petržlenová vňať 50g', 'Majorán čerstvý 50g',
        'Bazalka čerstvá 50g', 'Oregano čerstvé 50g', 'Tymián čerstvý 50g', 'Rozmarín čerstvý 50g',
        'Mäta čerstvá 50g', 'Šalvia čerstvá 50g', 'Estragón čerstvý 50g', 'Koriander čerstvý 50g',
        
        # Oils & Fats (20 items)
        'Olej slnečnicový 1l', 'Olej olivový 500ml', 'Olej kokosový 500ml', 'Maslo 250g',
        'Margarin 250g', 'Masť 200g', 'Lard 200g', 'Ghee 200g', 'Olej avokádový 250ml',
        'Olej ľanový 250ml', 'Olej sezamový 250ml', 'Olej arašidový 500ml', 'Olej repkový 1l',
        'Olej kukuričný 500ml', 'Olej ryžový 250ml', 'Olej vlašský 500ml', 'Maslo ghee 200g',
        'Margarin bez trans 250g', 'Masť husacia 200g', 'Masť kačacia 200g',
        
        # Spices & Seasonings (30 items)
        'Soľ 1kg', 'Soľ himalájska 500g', 'Soľ morská 500g', 'Cukor 1kg', 'Cukor trstinový 1kg',
        'Múka 1kg', 'Kypriaci prášok 200g', 'Soda bikarbóna 200g', 'Vanilkový cukor 200g',
        'Škorica 50g', 'Koriander 50g', 'Kmín 50g', 'Majorán 50g', 'Tymián 50g',
        'Rozmarín 50g', 'Bazalka 50g', 'Oregano 50g', 'Paprika sladká 100g', 'Paprika pikantná 100g',
        'Chilli prášok 50g', 'Kurkuma 50g', 'Zázvor 50g', 'Šafrán 1g', 'Vanilka 1ks',
        'Muškátový oriešok 50g', 'Štipľavá paprika 50g', 'Kardamóm 50g', 'Škoricový cukor 200g',
        'Cukor vanilkový 200g', 'Soľ čierna 500g',
        
        # Canned & Preserved (25 items)
        'Paradajková omáčka 500g', 'Kečup 500g', 'Horčica 200g', 'Majonéza 400g', 'Ocot 500ml',
        'Ocot vínny 500ml', 'Ocot jablkový 500ml', 'Sojová omáčka 250ml', 'Worcester omáčka 250ml',
        'Teriyaki omáčka 250ml', 'BBQ omáčka 500g', 'Česneková pasta 200g', 'Zázvorová pasta 200g',
        'Wasabi pasta 50g', 'Harissa pasta 200g', 'Pesto bazalkové 200g', 'Pesto česnekové 200g',
        'Pesto rajčiakové 200g', 'Hummus 200g', 'Tahini pasta 250g', 'Kokosové mlieko 400ml',
        'Mlieko mandľové 1l', 'Mlieko sójové 1l', 'Mlieko ovsené 1l', 'Mlieko kokosové 400ml',
        
        # Beverages (25 items)
        'Voda minerálna 1.5l', 'Voda pramenitá 1.5l', 'Džús jablkový 1l', 'Džús pomarančový 1l',
        'Džús višňový 1l', 'Džús jahodový 1l', 'Džús ananasový 1l', 'Džús grapefruitový 1l',
        'Čaj čierny 100g', 'Čaj zelený 100g', 'Čaj ovocný 100g', 'Čaj bylinkový 100g',
        'Káva mletá 250g', 'Káva instant 200g', 'Káva bez kofeínu 200g', 'Kakao 200g',
        'Kakao instant 200g', 'Cola 2l', 'Sprite 2l', 'Fanta 2l', 'Pivo svetlé 0.5l',
        'Pivo tmavé 0.5l', 'Víno biele 0.75l', 'Víno červené 0.75l', 'Limonáda citrón 2l',
        
        # Sweets & Snacks (35 items)
        'Čokoláda mliečna 100g', 'Čokoláda horká 100g', 'Čokoláda biela 100g', 'Čokoláda orechová 100g',
        'Bonbóny 200g', 'Žuvačky 100g', 'Cukríky 200g', 'Karamelky 200g', 'Sušené ovocie 200g',
        'Sušené banány 200g', 'Sušené jablká 200g', 'Orechy 200g', 'Orechy lieskové 200g',
        'Orechy vlašské 200g', 'Orechy mandľové 200g', 'Orechy kešu 200g', 'Orechy pistácie 200g',
        'Semienka 200g', 'Semienka slnečnicové 200g', 'Semienka tekvicové 200g', 'Popcorn 100g',
        'Čipsy 150g', 'Čipsy zemiakové 150g', 'Čipsy kukuričné 150g', 'Krekry 200g',
        'Sušienky 300g', 'Sušienky čokoládové 300g', 'Koláče 500g', 'Torty 1kg', 'Zmrzlina 500ml',
        'Zmrzlina vanilková 500ml', 'Zmrzlina čokoládová 500ml', 'Med 500g', 'Džem 400g',
        'Džem jahodový 400g', 'Nutella 400g', 'Marmeláda 400g', 'Sirup 500ml',
        
        # Frozen Foods (20 items)
        'Zmrazené jahody 500g', 'Zmrazené maliny 500g', 'Zmrazené brokolica 500g', 'Zmrazené karfiol 500g',
        'Zmrazené ryža 1kg', 'Zmrazené cestoviny 500g', 'Zmrazené pizza 400g', 'Zmrazené hranolky 1kg',
        'Zmrazené ryba 400g', 'Zmrazené mäso 500g', 'Zmrazené kuracie 500g', 'Zmrazené zelenina mix 500g',
        'Zmrazené ovocie mix 500g', 'Zmrazené špenát 300g', 'Zmrazené hrášok 500g', 'Zmrazené kukurica 500g',
        'Zmrazené brusnice 250g', 'Zmrazené čučoriedky 250g', 'Zmrazené čerešne 500g', 'Zmrazené bobuľový mix 500g',
        
        # Household & Cleaning (15 items)
        'Mýdlo 100g', 'Šampón 250ml', 'Sprchový gél 250ml', 'Zubná pasta 100ml', 'Zubná kefka 1ks',
        'Toaletný papier 8ks', 'Papierové utierky 100ks', 'Pracie prášok 3kg', 'Aviváž 1.5l', 'Čistič 500ml',
        'Čistič na okná 500ml', 'Čistič na podlahy 1l', 'Čistič na kúpeľňu 500ml', 'Saponát 500ml', 'Hubka 1ks',
        
        # Personal Care (15 items)
        'Parfum 50ml', 'Deodorant 150ml', 'Krém na ruky 100ml', 'Krém na tvár 50ml', 'Šampón na vlasy 250ml',
        'Kondicionér 250ml', 'Maskara 10ml', 'Rúž 5g', 'Puder 20g', 'Lak na nechty 10ml',
        'Pleťová voda 200ml', 'Čistič pleti 200ml', 'Krém na telo 200ml', 'Vlasový olej 100ml', 'Hrebeň 1ks',
        
        # Baby & Child (10 items)
        'Plienky 50ks', 'Mlieko pre deti 800g', 'Kaša pre deti 200g', 'Hračky 1ks', 'Oblečenie pre deti 1ks',
        'Deti šampón 200ml', 'Deti krém 100ml', 'Deti zubná pasta 50ml', 'Deti kefka 1ks', 'Deti uteráky 1ks',
        
        # Pet Food (10 items)
        'Krmivo pre psy 5kg', 'Krmivo pre mačky 5kg', 'Krmivo pre vtáky 1kg', 'Krmivo pre ryby 100g', 'Krmivo pre hlodavce 1kg',
        'Krmivo pre psy malé plemená 3kg', 'Krmivo pre psy veľké plemená 10kg', 'Krmivo pre mačky sterilizované 5kg', 'Mačacie konzervy 400g', 'Psie konzervy 400g',
        
        # Other (10 items)
        'Baterky 4ks', 'Žiarovky 5ks', 'Náradie 1ks', 'Knihy 1ks', 'Hračky 1ks',
        'Svietniky 2ks', 'Kľúče 1ks', 'Taška 1ks', 'Fľaša 1l', 'Kozmetická taška 1ks',
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
        # Suppress Google APIs GCM registration errors
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--mute-audio')
        options.add_argument('--no-first-run')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--disable-component-update')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-domain-reliability')
        options.add_argument('--disable-component-extensions-with-background-pages')
        # Additional options to suppress GCM errors
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-features=VizDisplayCompositor,VizHitTestSurfaceLayer')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
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