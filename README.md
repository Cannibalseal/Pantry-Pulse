# Pantry Pulse 🛒

## English

### Overview
**Pantry Pulse** is a real-time grocery price comparison web application that scrapes product prices from major Slovak supermarkets and displays price trends, inflation rates, and the best deals.

### Features
- 🔍 **Price Scraping**: Automatically scrapes 300+ products from 9 major stores (Tesco, Kaufland, Billa, Lidl, Penny, Albert, Coop, OKAY, Eurospar)
- 📊 **Price History**: Visual charts showing 90-day price trends and inflation rates
- 💰 **Best Prices**: Real-time display of lowest prices per product
- 🚀 **Fast Performance**: Optimized scraping with parallel store processing
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile
- 🔄 **Background Updates**: Automatic price updates without blocking the UI

### Tech Stack
- **Backend**: Flask (Python)
- **Database**: SQLite 
- **Scraping**: Selenium with Chrome WebDriver
- **Frontend**: Bootstrap 5, Chart.js
- **Logging**: Loguru

### Installation

#### Prerequisites
- Python 3.8+
- Chrome/Chromium browser
- Git

#### Steps
1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/pantry-pulse.git
   cd "Pantry Pulse"
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python run.py
   ```

5. **Access the web app**
   - Open browser: `http://127.0.0.1:5000`

### Usage

#### Browsing Products
- Homepage displays all 300+ products with emojis
- Click on any product to view detailed pricing
- See all stores and their current prices

#### Viewing Price History
- Each product page shows a 90-day price chart
- View inflation rate (% price change)
- See min/max prices in the period

#### Manual Scraping
- Click "Scrape Now" button to manually trigger price updates
- Updates run in background without blocking the page
- Check logs for scraping status

### Configuration

Create a `.env` file (copy from `.env.example`):
```env
FLASK_ENV=development
DEBUG=False
SECRET_KEY=your-secret-key-here
SCRAPE_INTERVAL_MINUTES=60
SELENIUM_HEADLESS=True
```

### Roadmap

#### 🚀 High Priority
- [ ] Search & filtering by product name/category
- [ ] Shopping list (add items, calculate total)
- [ ] Price alerts (notify when price drops)
- [ ] Mobile responsiveness improvements

#### 📊 Medium Priority
- [ ] Favorites/wishlist feature
- [ ] Admin dashboard
- [ ] Product comparison
- [ ] Pagination for product list

#### 💡 Lower Priority
- [ ] Dark mode
- [ ] User accounts
- [ ] Docker deployment
- [ ] Internationalization (EN, SK, CZ)

### Project Structure
```
Pantry Pulse/
├── pantry_pulse/
│   ├── __init__.py
│   ├── app.py              # Main Flask application
│   ├── config.py           # Configuration settings
│   ├── selenium_scraper.py # Web scraping logic
│   └── templates/          # HTML templates
├── run.py                  # Entry point
├── requirements.txt        # Python dependencies
├── TODO.md                 # Feature roadmap
└── README.md              # This file
```

### Troubleshooting

**Scraper not working?**
- Ensure Chrome is installed: `/Applications/Google Chrome.app` (macOS), `C:\Program Files\Google\Chrome\Application\chrome.exe` (Windows)
- Check internet connection
- Verify store websites are accessible

**Database errors?**
- Delete `pantry_pulse.db` and restart (will recreate cleanly)
- Check database path in `config.py`

**Performance issues?**
- Reduce `SCRAPE_INTERVAL_MINUTES` in `.env`
- Check logs with `tail -f app.log`

### License
MIT License - feel free to use commercially

### Contributing
Contributions welcome! Please:
1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## Slovenčina

### Popis
**Pantry Pulse** je webová aplikácia na porovnávanie cien potravín v reálnom čase, ktorá automaticky zbiera ceny produktov z veľkých slovenských supermarketov a zobrazuje trendy cien, mieru inflácie a najlepšie ponuky.

### Funkcie
- 🔍 **Zbieranie cien**: Automaticky zbiera ceny 300+ produktov z 9 veľkých stores (Tesco, Kaufland, Billa, Lidl, Penny, Albert, Coop, OKAY, Eurospar)
- 📊 **História cien**: Vizuálne grafy s trendmi cien za 90 dní a mierou inflácie
- 💰 **Najlepšie ceny**: Zobrazenie najnižších cien za produkty v reálnom čase
- 🚀 **Rýchly výkon**: Optimalizovaný scraping s paralelným spracovaním obchodov
- 📱 **Responzívny dizajn**: Funguje na desktope, tablete aj mobilných telefónoch
- 🔄 **Automatické aktualizácie**: Ceny sa aktualizujú na pozadí bez zablokovaného UI

### Technológia
- **Backend**: Flask (Python)
- **Databáza**: SQLite
- **Scraping**: Selenium s Chrome WebDriverom
- **Frontend**: Bootstrap 5, Chart.js
- **Logging**: Loguru

### Inštalácia

#### Požiadavky
- Python 3.8+
- Chrome/Chromium prehliadač
- Git

#### Kroky
1. **Klonujte repozitár**
   ```bash
   git clone https://github.com/vaseusername/pantry-pulse.git
   cd "Pantry Pulse"
   ```

2. **Vytvorte virtuálne prostredie**
   ```bash
   python -m venv venv
   # Na Windows:
   venv\Scripts\activate
   # Na macOS/Linux:
   source venv/bin/activate
   ```

3. **Nainštalujte závislosti**
   ```bash
   pip install -r requirements.txt
   ```

4. **Spustite aplikáciu**
   ```bash
   python run.py
   ```

5. **Otvorte webovú aplikáciu**
   - V prehliadači: `http://127.0.0.1:5000`

### Použitie

#### Prezeranie produktov
- Úvodná stránka zobrazuje všetkých 300+ produktov s emojis
- Kliknutím na produkt si pozrite podrobné ceny
- Vidíte všetky obchody a ich aktuálne ceny

#### Prezeranie histórie cien
- Každá stránka produktu obsahuje graf cien za 90 dní
- Vidíte mieru inflácie (% zmena ceny)
- Vidíte minimálne a maximálne ceny za period

#### Manuálne zbieranie cien
- Kliknutím na tlačidlo "Zbierať teraz" spustíte manuálnu aktualizáciu
- Aktualizácie sa vykonávajú na pozadí bez blokovania stránky
- Skontrolujte logy pre status zbierania

### Nastavenie

Vytvorte súbor `.env` (skopírujte z `.env.example`):
```env
FLASK_ENV=development
DEBUG=False
SECRET_KEY=your-secret-key-here
SCRAPE_INTERVAL_MINUTES=60
SELENIUM_HEADLESS=True
```

### Plán vývoja

#### 🚀 Vysoká priorita
- [ ] Vyhľadávanie a filtrovanie podľa názvu/kategórie
- [ ] Nákupný zoznam (pridávanie položiek, výpočet celkovej ceny)
- [ ] Upozornenia na ceny (notifikácia pri znížení ceny)
- [ ] Zlepšenie responzivity na mobilných zariadeniach

#### 📊 Stredná priorita
- [ ] Funkcia obľúbených/watchlistov
- [ ] Admin panel
- [ ] Porovnávanie produktov
- [ ] Paginacia zoznamu produktov

#### 💡 Nižšia priorita
- [ ] Tmavý režim
- [ ] Užívateľské účty
- [ ] Docker deployment
- [ ] Internacionalizácia (EN, SK, CZ)

### Štruktúra projektu
```
Pantry Pulse/
├── pantry_pulse/
│   ├── __init__.py
│   ├── app.py              # Hlavná Flask aplikácia
│   ├── config.py           # Nastavenia konfigurácie
│   ├── selenium_scraper.py # Logika web scrapingu
│   └── templates/          # HTML šablóny
├── run.py                  # Vstupný bod
├── requirements.txt        # Python závislosti
├── TODO.md                 # Plán vývoja
└── README.md              # Tento súbor
```

### Riešenie problémov

**Scraper nefunguje?**
- Uistite sa, že je Chrome nainštalovaný: `/Applications/Google Chrome.app` (macOS), `C:\Program Files\Google\Chrome\Application\chrome.exe` (Windows)
- Skontrolujte internetové pripojenie
- Overujte, či sú webové stránky obchodov dostupné

**Chyby databázy?**
- Vymažte `pantry_pulse.db` a reštartujte (bude sa obnovovať čisto)
- Skontrolujte cestu k databáze v `config.py`

**Problémy s výkonom?**
- Znížte `SCRAPE_INTERVAL_MINUTES` v `.env`
- Skontrolujte logy: `tail -f app.log`

### Licencia
MIT License - voľne použiteľné aj komerčne

### Prispievanie
Príspevky sú vítané! Prosím:
1. Forknite repozitár
2. Vytvorte feature branch (`git checkout -b feature/amazing-feature`)
3. Commitnite zmeny (`git commit -m 'Add amazing feature'`)
4. Pushujte na branch (`git push origin feature/amazing-feature`)
5. Otvorte Pull Request

---

**Made with ❤️ by Frank Buryan**
