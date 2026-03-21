import os
import threading
import base64
from urllib.parse import quote

from flask import Flask, render_template, request, flash, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from pantry_pulse.config import Config
from datetime import datetime, timedelta
from loguru import logger
from pantry_pulse.selenium_scraper import SeleniumScraper

# Configure logging
logger.add("app.log", rotation="1 MB", level="INFO")

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), default='Potraviny')
    unit = db.Column(db.String(20), default='')

class PriceEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref='price_entries')
    store = db.relationship('Store', backref='price_entries')


# --- Helper functions --------------------------------------------------------
def get_product_emoji(product_name):
    """Return an emoji that matches the product category"""
    name_lower = product_name.lower()
    emojis = {
        'mlieko': '🥛', 'jogurt': '🥛', 'smotana': '🥶', 'maslo': '🧈',
        'syr': '🧀', 'chlieb': '🍞', 'rožky': '🍞', 'croissant': '🥐',
        'cestoviny': '🍝', 'ryža': '🍚', 'zemiaky': '🥔', 'múka': '🌾',
        'paradajky': '🍅', 'paprika': '🌶️', 'okurky': '🥒', 'mrkva': '🥕',
        'cesnak': '🧄', 'cibula': '🧅', 'kapusta': '🥬', 'špenát': '🥬',
        'brokolica': '🥦', 'karfiol': '🥬',
        'banány': '🍌', 'jablká': '🍎', 'hruške': '🍐', 'pomaranče': '🍊',
        'citrón': '🍋', 'jahody': '🍓', 'maliny': '🫐', 'hrozno': '🍇',
        'broskyne': '🍑', 'melón': '🍈', 'ananás': '🍍', 'mango': '🥭',
        'kiwi': '🥝', 'kuracie': '🍗', 'hovädzie': '🥩', 'bravčové': '🍖',
        'ryba': '🐟', 'losos': '🐟', 'tuna': '🐟', 'sardíny': '🐟',
        'čokoláda': '🍫', 'sladkosti': '🍬', 'bonbóny': '🍬', 'karamel': '🍬',
        'medovina': '🍯', 'med': '🍯', 'marmeláda': '🍓', 'nutella': '🍫',
        'arašidové': '🥜', 'kokos': '🥥', 'orechy': '🌰',
        'čaj': '🫖', 'káva': '☕', 'voda': '💧', 'džús': '🧃', 'cola': '🥤',
        'pivo': '🍺', 'vino': '🍷',
        'olej': '🫧', 'soľ': '🧂', 'cukor': '🍬', 'ocot': '🫙', 'horčica': '🌭',
        'ketchup': '🍅', 'omáčka': '🍲', 'polievka': '🍲',
        'vajcia': '🥚', 'vejcia': '🥚', 'vagcia': '🥚',
        'zmrazené': '🧊', 'mrazené': '🧊', 'ľad': '🧊',
    }
    for key, emoji in emojis.items():
        if key in name_lower:
            return emoji
    return '🛒'  # Default


def get_product_image_url(product_name):
    """Generate a data URI SVG image with emoji for a product"""
    emoji = get_product_emoji(product_name)
    # Simple SVG with gradient and emoji
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#e8f5e9"/><stop offset="100%" style="stop-color:#c8e6c9"/></linearGradient></defs><rect width="180" height="180" rx="15" fill="url(#g)"/><text x="90" y="105" font-size="90" text-anchor="middle" dominant-baseline="middle">{emoji}</text></svg>'
    svg_bytes = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f'data:image/svg+xml;base64,{svg_bytes}'


# --- Background scraping helpers ------------------------------------------------
_scrape_lock = threading.Lock()
_is_scraping = False


def _get_latest_price_timestamp():
    latest = db.session.query(db.func.max(PriceEntry.timestamp)).scalar()
    return latest


def _scrape_interval_minutes():
    return int(os.environ.get('SCRAPE_INTERVAL_MINUTES', '60'))


def _should_scrape():
    latest = _get_latest_price_timestamp()
    if not latest:
        return True
    return datetime.utcnow() - latest > timedelta(minutes=_scrape_interval_minutes())


def _save_scraped_data(scraped_data, scraper):
    success_count = 0

    # Clear stale entries for stores/products we are updating, then recreate.
    for store_name, prices in scraped_data.items():
        store = Store.query.filter_by(name=store_name).first()
        if store:
            for product_name in prices.keys():
                product = Product.query.filter_by(name=product_name).first()
                if product:
                    PriceEntry.query.filter_by(product_id=product.id, store_id=store.id).delete()

    for store_name, prices in scraped_data.items():
        store = Store.query.filter_by(name=store_name).first()
        if not store:
            store = Store(name=store_name)
            db.session.add(store)
            db.session.flush()

        for product_name, price in prices.items():
            if price is None:
                continue

            product = Product.query.filter_by(name=product_name).first()
            if not product:
                product = Product(name=product_name)
                db.session.add(product)
                db.session.flush()

            # Ensure each store/product pair only has one active price entry at a time.
            PriceEntry.query.filter_by(product_id=product.id, store_id=store.id).delete()
            entry = PriceEntry(price=price, product_id=product.id, store_id=store.id)
            db.session.add(entry)
            success_count += 1

    db.session.commit()
    return success_count


def _scrape_and_update_db():
    global _is_scraping
    if _is_scraping:
        logger.info('Scrape already running; skipping')
        return

    with _scrape_lock:
        if _is_scraping:
            return
        _is_scraping = True

    try:
        logger.info('Starting background scrape')
        scraper = SeleniumScraper()
        scraped_data = scraper.scrape_all()
        with app.app_context():
            count = _save_scraped_data(scraped_data, scraper)
        logger.info(f'Background scrape completed: {count} prices saved')
    except Exception:
        logger.exception('Background scrape failed')
    finally:
        with app.app_context():
            db.session.remove()
        _is_scraping = False


def maybe_start_background_scrape():
    if _is_scraping:
        return

    if _should_scrape():
        threading.Thread(target=_scrape_and_update_db, daemon=True).start()


@app.route('/')
def index():
    products = Product.query.order_by(Product.name).all()
    if not products:
        flash('Aktualizácia prebieha na pozadí. Obnov stránku za chvíľu.')

    # Trigger an update if data is stale; this will run in the background.
    maybe_start_background_scrape()

    return render_template('index.html', products=products, get_product_image_url=get_product_image_url)

@app.route('/scrape', methods=['POST'])
def scrape():
    # Run scraping in the background to keep the UI responsive.
    threading.Thread(target=_scrape_and_update_db, daemon=True).start()
    flash('Scraping started in the background. Results will appear shortly.')
    return redirect(url_for('index'))

@app.route('/product/<slug>')
def product_detail(slug):
    # Ensure the app keeps updating prices in the background when users visit product pages.
    maybe_start_background_scrape()

    product_name = slug.replace('-', ' ').title()
    product = Product.query.filter(Product.name.ilike(product_name)).first()
    if not product:
        abort(404)

    entries = PriceEntry.query.filter_by(product_id=product.id).join(Store).order_by(PriceEntry.price.asc()).limit(50).all()
    return render_template('product_detail.html', product=product, entries=entries, product_id=product.id)

@app.route('/api/product/<slug>/history')
def product_history_api(slug):
    """Return historical price data for charting (last 90 days, average by day)"""
    from flask import jsonify
    
    product_name = slug.replace('-', ' ').title()
    product = Product.query.filter(Product.name.ilike(product_name)).first()
    if not product:
        abort(404)
    
    # Get all price entries for the last 90 days
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    entries = PriceEntry.query.filter(
        PriceEntry.product_id == product.id,
        PriceEntry.timestamp >= cutoff_date
    ).order_by(PriceEntry.timestamp.asc()).all()
    
    if not entries:
        return jsonify({'dates': [], 'prices': [], 'inflation_rate': 0})
    
    # Group by day and calculate average price per day
    daily_prices = {}
    for entry in entries:
        date_key = entry.timestamp.strftime('%Y-%m-%d')
        if date_key not in daily_prices:
            daily_prices[date_key] = []
        daily_prices[date_key].append(entry.price)
    
    # Calculate daily averages
    dates = sorted(daily_prices.keys())
    prices = [sum(daily_prices[d]) / len(daily_prices[d]) for d in dates]
    
    # Calculate inflation rate (% change from start to end)
    inflation_rate = 0
    if prices:
        inflation_rate = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] > 0 else 0
    
    return jsonify({
        'dates': dates,
        'prices': prices,
        'inflation_rate': round(inflation_rate, 2),
        'current_price': prices[-1] if prices else 0,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 0
    })

@app.route('/api/product/<int:product_id>/history')
def product_history(product_id):
    """Return historical price data for charting (last 90 days, average by day)"""
    from flask import jsonify
    
    product = Product.query.get(product_id)
    if not product:
        abort(404)
    
    # Get all price entries for the last 90 days
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    entries = PriceEntry.query.filter(
        PriceEntry.product_id == product_id,
        PriceEntry.timestamp >= cutoff_date
    ).order_by(PriceEntry.timestamp.asc()).all()
    
    if not entries:
        return jsonify({'dates': [], 'prices': [], 'inflation_rate': 0})
    
    # Group by day and calculate average price per day
    daily_prices = {}
    for entry in entries:
        date_key = entry.timestamp.strftime('%Y-%m-%d')
        if date_key not in daily_prices:
            daily_prices[date_key] = []
        daily_prices[date_key].append(entry.price)
    
    # Calculate daily averages
    dates = sorted(daily_prices.keys())
    prices = [sum(daily_prices[d]) / len(daily_prices[d]) for d in dates]
    
    # Calculate inflation rate (% change from start to end)
    inflation_rate = 0
    if prices:
        inflation_rate = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] > 0 else 0
    
    return jsonify({
        'dates': dates,
        'prices': prices,
        'inflation_rate': round(inflation_rate, 2),
        'current_price': prices[-1] if prices else 0,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 0
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info("Live Scraper App on http://127.0.0.1:5000")
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))

