import os
import threading
import base64
import re
import unicodedata
from urllib.parse import quote

from flask import Flask, render_template, request, flash, redirect, url_for, abort, jsonify
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
def get_product_category(product_name):
    """Assign a category to a product based on its name"""
    name_lower = normalize_product_name(product_name)
    
    category_keywords = {
        'Mliečne produkty': [
            'mlieko', 'jogurt', 'smotana', 'maslo', 'margarin', 'syr', 'tvaroh', 'kefír', 'šľahačka',
            'biely jogurt', 'vanilkový jogurt', 'grécky jogurt', 'nízkotučný', 'bez laktózy',
            'ovocné mlieko', 'mliečna zmrzlina', 'kyslá smotana', 'tvarohový dezert', 'ricotta',
            'cottage', 'feta', 'mozarella', 'gouda', 'eidam', 'parenice', 'oravský', 'bryndzový',
            'liptovský'
        ],
        'Pekáreň': [
            'chlieb', 'rožky', 'croissant', 'slnečnica', 'syrečky', 'žemľa', 'obloženka', 'bageta',
            'baguette', 'ciabatta', 'focaccia', 'donut', 'rozuk', 'buchty', 'koláče', 'chlebíčky',
            'maslové', 'makové', 'tvarohové', 'orechový', 'mini', 'ziemle', 'ziemľa'
        ],
        'Cestoviny & Obilniny': [
            'cestoviny', 'špagety', 'penne', 'fusilli', 'farfalle', 'lasagne', 'makaróny', 'rezance',
            'bez lepku', 'celozrnné', 'ryža', 'basmati', 'jazmínová', 'parboiled', 'čierna ryža',
            'divoká ryža', 'kuskus', 'quinoa', 'bulgur', 'jačmeň', 'proso', 'šošovica', 'fazuľa',
            'hrach', 'cizrna', 'červená šošovica', 'zelená šošovica', 'múka', 'pšeničná', 'ražná',
            'kukuričná', 'špaldová', 'kokosová', 'mandľová', 'ryžová', 'pohánková', 'krupica',
            'ovsené vločky', 'špaldové vločky', 'jačmenné vločky', 'pšeničné vločky', 'kukuričné vločky',
            'instant', 'na lívance', 'na chlieb', 'na pečenie', 'čirok', 'amarant', 'pohánka'
        ],
        'Zelenina': [
            'zemiaky', 'cibuľa', 'cesnak', 'mrkva', 'petržlen', 'zeler', 'paradajky', 'uhorky',
            'paprika', 'baklažán', 'špenát', 'šalát', 'kaleráb', 'karfiol', 'brokolica', 'kapusta',
            'kukurica', 'špargľa', 'reďkovka', 'rettich', 'tekvica', 'cuketa', 'fazuľové struky',
            'hrachový struky', 'špenátový list', 'hlávkový', 'ľadový', 'rukola', 'baby', 'kôpor',
            'petržlenová vňať', 'majorán čerstvý', 'bazalka čerstvá', 'oregano čerstvé', 'tymián čerstvý',
            'rozmarín čerstvý', 'mäta čerstvá', 'šalvia čerstvá', 'estragón čerstvý', 'koriander čerstvý'
        ],
        'Ovocie': [
            'banány', 'jablká', 'hrušky', 'broskyne', 'marhule', 'slivky', 'čerešne', 'višne',
            'maliny', 'jahody', 'borievky', 'pomaranče', 'mandarínky', 'citróň', 'ananás',
            'červené', 'zelené', 'biele hrozno', 'červené hrozno', 'kiwi', 'mango', 'avokádo',
            'granátové jablko', 'papája', 'dragon fruit', 'limetka', 'grapefruit', 'nektarínky',
            'brokvica', 'ríbezle', 'egreše', 'ostružiny', 'durian', 'karambola'
        ],
        'Mäso & Ryby': [
            'kuracie', 'stehná', 'krídla', 'celé', 'filet', 'miesko', 'hovädzie', 'steak', 'guláš',
            'rebrá', 'svíčková', 'bravčové', 'chrbtica', 'kotlety', 'panenka', 'morská ryba', 'losos',
            'treska', 'šťuka', 'zubatka', 'klobása', 'pražská', 'debrecínska', 'špikovaná slanina',
            'slanina', 'sliepkové', 'jahňacia', 'jahňacie', 'bravčová pečeň', 'ryba pstruh', 'kapor',
            'mäso na guláš', 'mleté kuracie', 'mleté hovädzie', 'mleté bravčové', 'tuna konzervovaná'
        ],
        'Sladkosti': [
            'čokoláda', 'mliečna', 'horká', 'biela', 'orechová', 'bonbóny', 'žuvačky', 'cukríky',
            'karamelky', 'sušené ovocie', 'sušené banány', 'sušené jablká', 'orechy', 'lieskové',
            'vlašské', 'mandľové', 'kešu', 'pistácie', 'semienka', 'slnečnicové', 'tekvicové',
            'popcorn', 'čipsy', 'zemiakové', 'kukuričné', 'krekry', 'sušienky', 'čokoládové',
            'koláče', 'torty', 'zmrzlina', 'vanilková', 'čokoládová', 'med', 'džem', 'jahodový',
            'nutella', 'marmeláda', 'sirup'
        ],
        'Orechové produkty': [
            'arašidové', 'kokos', 'orechy', 'mandľa', 'lieskový', 'pistácie', 'kešu'
        ],
        'Nápoje': [
            'minerálna voda', 'pramenitá voda', 'jablkový džús', 'pomarančový džús', 'višňový džús',
            'jahodový džús', 'ananásový džús', 'grapefruitový džús', 'čierny čaj', 'zelený čaj',
            'ovocný čaj', 'bylinkový čaj', 'mletá káva', 'instant káva', 'bez kofeínu', 'kakao',
            'instant kakao', 'cola', 'sprite', 'fanta', 'svetlé pivo', 'tmavé pivo', 'biele víno',
            'červené víno', 'limonáda', 'citrón', 'čaj', 'káva', 'voda', 'džús', 'pivo', 'víno'
        ],
        'Korenia & Koreniny': [
            'olej', 'slnečnicový', 'olivový', 'kokosový', 'avokádový', 'ľanový', 'sezamový', 'arašidový',
            'repkový', 'kukuričný', 'ryžový', 'vlašský', 'ghee', 'bez trans', 'husacia', 'kačacia',
            'soľ', 'himalájska', 'morská', 'cukor', 'trstinový', 'kypriaci prášok', 'soda bikarbóna',
            'vanilkový cukor', 'škorica', 'koriander', 'kmín', 'majorán', 'tymián', 'rozmarín', 'bazalka',
            'oregano', 'paprika', 'sladká', 'pikantná', 'chilli', 'kurkuma', 'zázvor', 'šafrán', 'vanilka',
            'muškátový oriešok', 'štipľavá', 'kardamóm', 'škoricový', 'čierna soľ', 'paradajková omáčka',
            'kečup', 'horčica', 'majonéza', 'ocot', 'vínny', 'jablkový', 'sojová omáčka', 'worcester',
            'teriyaki', 'bbq omáčka', 'česneková pasta', 'zázvorová pasta', 'wasabi', 'harissa', 'pesto',
            'bazalkové', 'česnekové', 'rajčiakové', 'hummus', 'tahini', 'kokosové mlieko', 'mandľové mlieko',
            'sójové mlieko', 'ovsené mlieko'
        ],
        'Vajcia': [
            'vajcia', 'vejcia', 'vagcia', 'bio', 'voľný chov', 'bez klietok', 'čerstvé'
        ],
        'Zmrazené potraviny': [
            'zmrazené', 'mrazené', 'ľad', 'frites', 'pelmeni', 'pizza', 'kura', 'ryba', 'mix',
            'hrášok', 'kukurica', 'brusnice', 'čučoriedky', 'čerešne', 'bobuľový mix'
        ],
    }
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            normalized_keyword = normalize_product_name(keyword)
            if normalized_keyword and normalized_keyword in name_lower:
                return category
    
    return 'Ostatné'


def get_product_emoji(product_name):
    """Return an emoji that matches the product category"""
    name_lower = product_name.lower()
    emojis = {
        'mlieko': '🥛', 'jogurt': '🥛', 'smotana': '🥶', 'maslo': '🧈',
        'syr': '🧀', 'kefír': '🥛', 'šľahačka': '🥛', 'tvaroh': '🥛',
        'chlieb': '🍞', 'rožky': '🍞', 'croissant': '🥐', 'žemľa': '🥖',
        'bageta': '🥖', 'baguette': '🥖', 'ciabatta': '🥖', 'focaccia': '🥖',
        'cestoviny': '🍝', 'ryža': '🍚', 'zemiaky': '🥔', 'múka': '🌾',
        'krupica': '🌾', 'pohánka': '🌾', 'amarant': '🌾', 'quinoa': '🌾',
        'paradajky': '🍅', 'paprika': '🌶️', 'okurky': '🥒', 'mrkva': '🥕',
        'cesnak': '🧄', 'cibula': '🧅', 'kapusta': '🥬', 'špenát': '🥬',
        'brokolica': '🥦', 'karfiol': '🥬', 'kaleráb': '🥬', 'špargľa': '🥬',
        'banány': '🍌', 'jablká': '🍎', 'hruške': '🍐', 'pomaranče': '🍊',
        'citrón': '🍋', 'jahody': '🍓', 'maliny': '🫐', 'hrozno': '🍇',
        'broskyne': '🍑', 'melón': '🍈', 'ananás': '🍍', 'mango': '🥭',
        'kiwi': '🥝', 'slivka': '🍇', 'marhule': '🍑', 'čerešne': '🍒',
        'kuracie': '🍗', 'hovädzie': '🥩', 'bravčové': '🍖', 'ryba': '🐟',
        'losos': '🐟', 'tuna': '🐟', 'sardíny': '🐟', 'klobása': '🌭',
        'slanina': '🥓', 'jahňacia': '🍖', 'mleté': '🥩',
        'čokoláda': '🍫', 'sladkosti': '🍬', 'bonbóny': '🍬', 'karamel': '🍬',
        'medovina': '🍯', 'med': '🍯', 'marmeláda': '🍓', 'nutella': '🍫',
        'sušené ovocie': '🍇', 'orechy': '🌰', 'semienka': '🌰', 'popcorn': '🍿',
        'arašidové': '🥜', 'kokos': '🥥', 'mandľa': '🌰', 'lieskový': '🌰',
        'čaj': '🫖', 'káva': '☕', 'voda': '💧', 'džús': '🧃', 'cola': '🥤',
        'pivo': '🍺', 'vino': '🍷', 'limonáda': '🥤',
        'olej': '🫧', 'soľ': '🧂', 'cukor': '🍬', 'ocot': '🫙', 'horčica': '🌭',
        'ketchup': '🍅', 'omáčka': '🍲', 'polievka': '🍲',
        'škorica': '🫙', 'koriander': '🫙', 'kmín': '🫙', 'majorán': '🫙',
        'tymián': '🫙', 'rozmarín': '🫙', 'bazalka': '🫙', 'oregano': '🫙',
        'paprika sladká': '🫙', 'kurkuma': '🫙', 'zázvor': '🫙', 'vanilka': '🫙',
        'vajcia': '🥚', 'vejcia': '🥚', 'vagcia': '🥚',
        'zmrazené': '🧊', 'mrazené': '🧊', 'ľad': '🧊', 'frites': '🍟',
        'pelmeni': '🥟', 'pizza': '🍕',
    }
    for key, emoji in emojis.items():
        if key in name_lower:
            return emoji
    return '🛒'  # Default


def normalize_product_name(product_name):
    """Normalize product name for accent-insensitive matching"""
    if not product_name:
        return ''
    name = product_name.strip().lower()
    # Convert accented characters to ascii equivalents
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(ch for ch in name if not unicodedata.combining(ch))
    # Normalize whitespace and punctuation to spaces
    name = re.sub(r'[^a-z0-9]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_product_image_url(product_name):
    """Return a stock image URL for a product based on its category"""
    category = get_product_category(product_name)
    name_lower = normalize_product_name(product_name)
    
    # Category-based image URLs (using free stock photo services)
    category_images = {
        'Mliečne produkty': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'Pekáreň': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'Cestoviny & Obilniny': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'Zelenina': 'https://images.unsplash.com/photo-1566385101042-1a0aa0c1268c?w=400&h=400&fit=crop',
        'Ovocie': 'https://images.unsplash.com/photo-1619566636858-adf2597f7335?w=400&h=400&fit=crop',
        'Mäso & Ryby': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'Sladkosti': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'Orechové produkty': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'Nápoje': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'Korenia & Koreniny': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'Vajcia': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'Zmrazené potraviny': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
    }
    
    # Specific product images - much more detailed and specific
    specific_images = {
        # Dairy Products - Very specific
        'mlieko plnotučná': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mlieko polotučná': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mlieko nízkotučná': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mlieko bez laktózy': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=400&fit=crop',
        'mlieko ovocné jablko': 'https://images.unsplash.com/photo-1628771065518-0d82f1938462?w=400&h=400&fit=crop',
        'mlieko ovocné čokoláda': 'https://images.unsplash.com/photo-1607478900766-efe13248b125?w=400&h=400&fit=crop',
        'mlieko ovocné vanilka': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'jogurt prírodný': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'jogurt ovocný': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'grécky jogurt': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'jogurt nízkotučný': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'jogurt biely': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'jogurt vanilkový': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'jogurt čokoládový': 'https://images.unsplash.com/photo-1607478900766-efe13248b125?w=400&h=400&fit=crop',
        'jogurt jahodový': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=400&fit=crop',
        'jogurt banánový': 'https://images.unsplash.com/photo-1628771065518-0d82f1938462?w=400&h=400&fit=crop',
        'kefír': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'tvaroh': 'https://images.unsplash.com/photo-1628088062854-d1870b4553da?w=400&h=400&fit=crop',
        'smotana': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'šľahačka': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'maslo tradičné': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'maslo nízkotučné': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'margarin': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'syr parenice': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr oravský': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr eidam': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr gouda': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr mozzarella': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr feta': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr cottage': 'https://images.unsplash.com/photo-1628088062854-d1870b4553da?w=400&h=400&fit=crop',
        'syr ricotta': 'https://images.unsplash.com/photo-1628088062854-d1870b4553da?w=400&h=400&fit=crop',
        'kyslá smotana': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mliečna zmrzlina vanilka': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'mliečna zmrzlina čokoláda': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'mliečna zmrzlina jahoda': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'mlieko 2.5% 1l': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mlieko 3.5% 1l': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'mlieko bez laktózy nízkotučná 1l': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=400&fit=crop',
        'kefír nízkotučný 500ml': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'tvaroh nízkotučný 250g': 'https://images.unsplash.com/photo-1628088062854-d1870b4553da?w=400&h=400&fit=crop',
        'smotana 200ml 18%': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'smotana 200ml 36%': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'smotana na šľahanie 200ml': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'margarin ľahký 250g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'syr parenice 250g': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr bryndzový 200g': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'syr liptovský 200g': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'biely jogurt 150g': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'vanilkový jogurt 150g': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'šľahačka 200ml': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'šľahačka na šľahanie 500ml': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'kyslá smotana 200g': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'kyslá smotana ľahká 200g': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        
        # Eggs - Very specific sizes
        'vajcia s': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia l': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia xl': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia m': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia bio': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia voľný chov': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia bez klietok': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'vajcia čerstvé': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        
        # Meat & Fish - Very specific
        'kuracie prsia': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie stehná': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'mleté kuracie': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie krídla': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie celé': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie filet': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie miesko': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'hovädzie steak': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie guláš': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'mleté hovädzie': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie rebrá': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie svíčková': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'bravčové stehno': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'mleté bravčové': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová chrbtica': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčové kotlety': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová panenka': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová pečeň': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'mäso na guláš': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'morská ryba filet': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'losos filet': 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=400&h=400&fit=crop',
        'treska filet': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'šťuka filet': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'zubatka filet': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba pstruh': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba kapor': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba zubatka': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'tuna konzervovaná': 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400&h=400&fit=crop',
        'klobása domáca': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'klobása pražská': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'klobása debrecínska': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'špikovaná slanina': 'https://images.unsplash.com/photo-1529042410759-befb1204b468?w=400&h=400&fit=crop',
        'slanina domáca': 'https://images.unsplash.com/photo-1529042410759-befb1204b468?w=400&h=400&fit=crop',
        'sliepkové prsia': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'jahňacia mäso': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'kuracie celé 1.5kg': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie filet 500g': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'kuracie miesko 1kg': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'hovädzie steak 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie guláš 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'mleté hovädzie 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie rebrá 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'hovädzie svíčková 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'bravčové stehno 1kg': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'mleté bravčové 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová chrbtica 1kg': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčové kotlety 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová panenka 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'bravčová pečeň 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'mäso na guláš 500g': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'morská ryba filet 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'losos filet 400g': 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=400&h=400&fit=crop',
        'treska filet 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'šťuka filet 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'zubatka filet 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba pstruh 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba kapor 1kg': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'ryba zubatka 400g': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'tuna konzervovaná 185g': 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400&h=400&fit=crop',
        'klobása domáca 400g': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'klobása pražská 400g': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'klobása debrecínska 400g': 'https://images.unsplash.com/photo-1551782450-17144efb5723?w=400&h=400&fit=crop',
        'špikovaná slanina 200g': 'https://images.unsplash.com/photo-1529042410759-befb1204b468?w=400&h=400&fit=crop',
        'slanina domáca 300g': 'https://images.unsplash.com/photo-1529042410759-befb1204b468?w=400&h=400&fit=crop',
        'sliepkové prsia 500g': 'https://images.unsplash.com/photo-1608039755401-5131f1d3b643?w=400&h=400&fit=crop',
        'jahňacia mäso 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        'jahňacie kotlety 500g': 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&h=400&fit=crop',
        
        # Bakery - Very specific
        'chlieb klasický': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb žitný': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb bez lepku': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb bielý': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb čierny': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'valcový chlieb': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'kváskový chlieb': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'grahamový chlieb': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb pšeničný': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb ražný': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'chlieb špaldový': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'rozuk': 'https://images.unsplash.com/photo-1495147466023-ac5c588e2e94?w=400&h=400&fit=crop',
        'rožky': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'rožky maslové': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'croissant vanila': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'croissant čokoláda': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'croissant maslový': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'donut': 'https://images.unsplash.com/photo-1551024506-0bccd828d307?w=400&h=400&fit=crop',
        'donut čokoládový': 'https://images.unsplash.com/photo-1551024506-0bccd828d307?w=400&h=400&fit=crop',
        'syrečky chlieb': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'žemľa syrová': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'žemľa maslová': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka koprivnica': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka salát': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka šunka': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlieb s orechovcom': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'kváskový chlieb kváska': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'bageta': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'baguette': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'mini žemle': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'ciabatta': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'focaccia': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlebíčky': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlebíčky maslové': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty makové': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty tvarohové': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'koláče': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'koláče makový': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'syrečky chlieb 150g': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'syrečky chlieb 500g': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'žemľa syrová 1ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'žemľa maslová 1ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka koprivnica 1ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka salát 1ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'obloženka šunka 1ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlieb s orechovcom 500g': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'kváskový chlieb kváska 300g': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'bageta 300g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'baguette 300g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'mini žemle 4ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'ciabatta 250g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'focaccia 300g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlebíčky 6ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'chlebíčky maslové 6ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty 4ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty makové 4ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'buchty tvarohové 4ks': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'koláče 500g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'koláče makový 500g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        'koláče orechový 500g': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400&h=400&fit=crop',
        
        # Pasta & Grains - Very specific
        'cestoviny': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny špagety': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny penne': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny fusilli': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny farfalle': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny lasagne': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny makaróny': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny rezance': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny bez lepku': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny celozrnné': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'ryža': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža basmati': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža jazmínová': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža parboiled': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža čierna': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža divoká': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'kuskus': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'quinoa': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'bulgur': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'jačmeň': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'proso': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'fazuľa': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'hrach': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'cizrna': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica červená': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica zelená': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná hrubá': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná polohrúbka': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná jemná': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná hrubá': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná polohrúbka': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná jemná': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka kukuričná': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka špaldová': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka kokosová': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka mandľová': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ryžová': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pohánková': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'krupica': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'ovsené vločky': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'ovsené vločky instant': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'pohánka': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'amarant': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'čirok': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'špaldové vločky': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'jačmenné vločky': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'pšeničné vločky': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'kukuričné vločky': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka na lívance': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka na chlieb': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'cestoviny 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny špagety 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny penne 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny fusilli 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny farfalle 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny lasagne 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny makaróny 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny rezance 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny bez lepku 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'cestoviny celozrnné 500g': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'ryža 1kg': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža basmati 1kg': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža jazmínová 1kg': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža parboiled 1kg': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža čierna 500g': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ryža divoká 500g': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'kuskus 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'quinoa 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'bulgur 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'jačmeň 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'proso 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'fazuľa 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'hrach 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'cizrna 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica červená 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'šošovica zelená 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná hrubá 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná polohrúbka 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pšeničná jemná 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná hrubá 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná polohrúbka 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ražná jemná 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka kukuričná 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka špaldová 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka kokosová 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka mandľová 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka ryžová 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka pohánková 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'krupica 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'ovsené vločky 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'ovsené vločky instant 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'pohánka 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'amarant 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'čirok 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'špaldové vločky 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'jačmenné vločky 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'pšeničné vločky 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'kukuričné vločky 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka na lívance 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka na chlieb 1kg': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'múka na pečenie 500g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        
        # Fruits - Very specific
        'jablká': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'jablká červené': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'jablká zelené': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'hrušky': 'https://images.unsplash.com/photo-1514756331096-242fdeb70d4a?w=400&h=400&fit=crop',
        'broskyne': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'marhule': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'slivky': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'čerešne': 'https://images.unsplash.com/photo-1528821128474-27f963b062bf?w=400&h=400&fit=crop',
        'višne': 'https://images.unsplash.com/photo-1528821128474-27f963b062bf?w=400&h=400&fit=crop',
        'maliny': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'jahody': 'https://images.unsplash.com/photo-1601004890684-d8cbf643f5f2?w=400&h=400&fit=crop',
        'borievky': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'banány': 'https://images.unsplash.com/photo-1571771019784-3ff35f4f4277?w=400&h=400&fit=crop',
        'pomaranče': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'mandarínky': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'citróň': 'https://images.unsplash.com/photo-1587734195503-904fca47e0ec?w=400&h=400&fit=crop',
        'ananás': 'https://images.unsplash.com/photo-1550258987-190a2d41a8ba?w=400&h=400&fit=crop',
        'hrozno biele': 'https://images.unsplash.com/photo-1537640538966-79f36943f303?w=400&h=400&fit=crop',
        'hrozno červené': 'https://images.unsplash.com/photo-1537640538966-79f36943f303?w=400&h=400&fit=crop',
        'kiwi': 'https://images.unsplash.com/photo-1585059895524-72359e06133a?w=400&h=400&fit=crop',
        'mango': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'avokádo': 'https://images.unsplash.com/photo-1523049673857-eb18f1d7b578?w=400&h=400&fit=crop',
        'granátové jablko': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400&h=400&fit=crop',
        'papája': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'dragon fruit': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'limetka': 'https://images.unsplash.com/photo-1587734195503-904fca47e0ec?w=400&h=400&fit=crop',
        'grapefruit': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'nektarínky': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'brokvica': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'ríbezle červené': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'ríbezle čierne': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'egreše': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'ostružiny': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'durian': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'jablká 1kg': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'jablká červené 1kg': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'jablká zelené 1kg': 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop',
        'hrušky 1kg': 'https://images.unsplash.com/photo-1514756331096-242fdeb70d4a?w=400&h=400&fit=crop',
        'broskyne 500g': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'marhule 500g': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'slivky 1kg': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'čerešne 500g': 'https://images.unsplash.com/photo-1528821128474-27f963b062bf?w=400&h=400&fit=crop',
        'višne 500g': 'https://images.unsplash.com/photo-1528821128474-27f963b062bf?w=400&h=400&fit=crop',
        'maliny 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'jahody 500g': 'https://images.unsplash.com/photo-1601004890684-d8cbf643f5f2?w=400&h=400&fit=crop',
        'borievky 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'banány 1kg': 'https://images.unsplash.com/photo-1571771019784-3ff35f4f4277?w=400&h=400&fit=crop',
        'pomaranče 1kg': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'mandarínky 1kg': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'citróň 1ks': 'https://images.unsplash.com/photo-1587734195503-904fca47e0ec?w=400&h=400&fit=crop',
        'ananás 1ks': 'https://images.unsplash.com/photo-1550258987-190a2d41a8ba?w=400&h=400&fit=crop',
        'hrozno biele 1kg': 'https://images.unsplash.com/photo-1537640538966-79f36943f303?w=400&h=400&fit=crop',
        'hrozno červené 1kg': 'https://images.unsplash.com/photo-1537640538966-79f36943f303?w=400&h=400&fit=crop',
        'kiwi 500g': 'https://images.unsplash.com/photo-1585059895524-72359e06133a?w=400&h=400&fit=crop',
        'mango 1ks': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'avokádo 1ks': 'https://images.unsplash.com/photo-1523049673857-eb18f1d7b578?w=400&h=400&fit=crop',
        'granátové jablko 1ks': 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=400&h=400&fit=crop',
        'papája 1ks': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'dragon fruit 1ks': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'limetka 1ks': 'https://images.unsplash.com/photo-1587734195503-904fca47e0ec?w=400&h=400&fit=crop',
        'grapefruit 1ks': 'https://images.unsplash.com/photo-1557800636-894a64c1696f?w=400&h=400&fit=crop',
        'nektarínky 500g': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'brokvica 500g': 'https://images.unsplash.com/photo-1538829658229-6a0e5070886d?w=400&h=400&fit=crop',
        'ríbezle červené 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'ríbezle čierne 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'egreše 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'ostružiny 250g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'durian 1ks': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        'karambola 1ks': 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=400&h=400&fit=crop',
        
        # Vegetables - Very specific
        'zemiaky': 'https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400&h=400&fit=crop',
        'cibuľa': 'https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=400&h=400&fit=crop',
        'cesnak': 'https://images.unsplash.com/photo-1540148426945-6cf22a6b4faf?w=400&h=400&fit=crop',
        'mrkva': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'petržlen': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'zeler': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'paradajky': 'https://images.unsplash.com/photo-1546470427-e9e85214c45c?w=400&h=400&fit=crop',
        'uhorky': 'https://images.unsplash.com/photo-1449300079323-02e209d9d3a?w=400&h=400&fit=crop',
        'paprika': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=400&h=400&fit=crop',
        'baklažán': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=400&h=400&fit=crop',
        'špenát': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'šalát': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'kaleráb': 'https://images.unsplash.com/photo-1584270354949-c26b0d5b4a0?w=400&h=400&fit=crop',
        'karfiol': 'https://images.unsplash.com/photo-1568584711075-3d021a7c3ca?w=400&h=400&fit=crop',
        'brokolica': 'https://images.unsplash.com/photo-1459411621453-7c98d3a32465?w=400&h=400&fit=crop',
        'kapusta': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'kukurica': 'https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=400&h=400&fit=crop',
        'špargľa': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'reďkovka': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'rettich': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'tekvica': 'https://images.unsplash.com/photo-1570197788417-0e82375c9371?w=400&h=400&fit=crop',
        'cuketa': 'https://images.unsplash.com/photo-1570197788417-0e82375c9371?w=400&h=400&fit=crop',
        'fazuľové struky': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'hrachový struky': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'špenátový list': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'šalát hlávkový': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'šalát ľadový': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'rukola': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'špenát baby': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'kôpor': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'petržlenová vňať': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'majorán čerstvý': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'bazalka čerstvá': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'oregano čerstvé': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'tymián čerstvý': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'rozmarín čerstvý': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'mäta čerstvá': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'šalvia čerstvá': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'estragón čerstvý': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'zemiaky 1kg': 'https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400&h=400&fit=crop',
        'cibuľa 1kg': 'https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=400&h=400&fit=crop',
        'cesnak 200g': 'https://images.unsplash.com/photo-1540148426945-6cf22a6b4faf?w=400&h=400&fit=crop',
        'mrkva 1kg': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'petržlen 1ks': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'zeler 1ks': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'paradajky 1kg': 'https://images.unsplash.com/photo-1546470427-e9e85214c45c?w=400&h=400&fit=crop',
        'uhorky 1kg': 'https://images.unsplash.com/photo-1449300079323-02e209d9d3a?w=400&h=400&fit=crop',
        'paprika 1kg': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=400&h=400&fit=crop',
        'baklažán 1ks': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=400&h=400&fit=crop',
        'špenát 300g': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'šalát 1ks': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'kaleráb 1ks': 'https://images.unsplash.com/photo-1584270354949-c26b0d5b4a0?w=400&h=400&fit=crop',
        'karfiol 1ks': 'https://images.unsplash.com/photo-1568584711075-3d021a7c3ca?w=400&h=400&fit=crop',
        'brokolica 500g': 'https://images.unsplash.com/photo-1459411621453-7c98d3a32465?w=400&h=400&fit=crop',
        'kapusta 1ks': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'kukurica 1ks': 'https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=400&h=400&fit=crop',
        'špargľa 500g': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'reďkovka 500g': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'rettich 1ks': 'https://images.unsplash.com/photo-1582515073490-39981397c445?w=400&h=400&fit=crop',
        'tekvica 1kg': 'https://images.unsplash.com/photo-1570197788417-0e82375c9371?w=400&h=400&fit=crop',
        'cuketa 1kg': 'https://images.unsplash.com/photo-1570197788417-0e82375c9371?w=400&h=400&fit=crop',
        'fazuľové struky 500g': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'hrachový struky 500g': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'špenátový list 300g': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'šalát hlávkový 1ks': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'šalát ľadový 1ks': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'rukola 100g': 'https://images.unsplash.com/photo-1559054663-8a3a9c41c507?w=400&h=400&fit=crop',
        'špenát baby 150g': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400&h=400&fit=crop',
        'kôpor 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'petržlenová vňať 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'majorán čerstvý 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'bazalka čerstvá 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'oregano čerstvé 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'tymián čerstvý 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'rozmarín čerstvý 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'mäta čerstvá 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'šalvia čerstvá 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'estragón čerstvý 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        'koriander čerstvý 50g': 'https://images.unsplash.com/photo-1618375569909-3c8616cf09ae?w=400&h=400&fit=crop',
        
        # Oils & Fats - Very specific
        'olej slnečnicový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej olivový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej kokosový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'maslo': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'margarin': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'lard': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'ghee': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'olej avokádový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej ľanový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej sezamový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej arašidový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej repkový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej kukuričný': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej ryžový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej vlašský': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'maslo ghee': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'margarin bez trans': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť husacia': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť kačacia': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        
        # Spices & Seasonings - Very specific
        'soľ': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'soľ himalájska': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'soľ morská': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'cukor': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'cukor trstinový': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'kypriaci prášok': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'soda bikarbóna': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'vanilkový cukor': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'škorica': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'koriander': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kmín': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'majorán': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'tymián': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'rozmarín': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'bazalka': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'oregano': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'paprika sladká': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'paprika pikantná': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'chilli prášok': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kurkuma': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'zázvor': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'šafrán': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'vanilka': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'muškátový oriešok': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'štipľavá paprika': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kardamóm': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'škoricový cukor': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'cukor vanilkový': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'olej slnečnicový 1l': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej olivový 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej kokosový 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'maslo 250g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'margarin 250g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'lard 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'ghee 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'olej avokádový 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej ľanový 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej sezamový 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej arašidový 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej repkový 1l': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej kukuričný 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej ryžový 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'olej vlašský 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'maslo ghee 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'margarin bez trans 250g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť husacia 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'masť kačacia 200g': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'soľ 1kg': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'soľ himalájska 500g': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'soľ morská 500g': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        'cukor 1kg': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'cukor trstinový 1kg': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'kypriaci prášok 200g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'soda bikarbóna 200g': 'https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?w=400&h=400&fit=crop',
        'vanilkový cukor 200g': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'škorica 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'koriander 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kmín 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'majorán 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'tymián 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'rozmarín 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'bazalka 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'oregano 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'paprika sladká 100g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'paprika pikantná 100g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'chilli prášok 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kurkuma 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'zázvor 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'šafrán 1g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'vanilka 1ks': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'muškátový oriešok 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'štipľavá paprika 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'kardamóm 50g': 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
        'škoricový cukor 200g': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'cukor vanilkový 200g': 'https://images.unsplash.com/photo-1581441363689-1f3c3c414635?w=400&h=400&fit=crop',
        'soľ čierna 500g': 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=400&fit=crop',
        
        # Canned & Preserved - Very specific
        'paradajková omáčka': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'kečup': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'horčica': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'majonéza': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot vínny': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot jablkový': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'sojová omáčka': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'worcester omáčka': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'teriyaki omáčka': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'bbq omáčka': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'česneková pasta': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'zázvorová pasta': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'wasabi pasta': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'harissa pasta': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto bazalkové': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto česnekové': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto rajčiakové': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'hummus': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'tahini pasta': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'kokosové mlieko': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko mandľové': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko sójové': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko ovsené': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        
        # Beverages - Very specific
        'voda minerálna': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'voda pramenitá': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'džús jablkový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús pomarančový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús višňový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús jahodový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús ananasový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús grapefruitový': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'čaj čierny': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj zelený': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj ovocný': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj bylinkový': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'káva mletá': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'káva instant': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'káva bez kofeínu': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'kakao': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'kakao instant': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'cola': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'sprite': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'fanta': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'pivo svetlé': 'https://images.unsplash.com/photo-1608270586620-248524c67de9?w=400&h=400&fit=crop',
        'pivo tmavé': 'https://images.unsplash.com/photo-1608270586620-248524c67de9?w=400&h=400&fit=crop',
        'víno biele': 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?w=400&h=400&fit=crop',
        'víno červené': 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?w=400&h=400&fit=crop',
        'limonáda citrón': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        
        # Sweets & Snacks - Very specific
        'čokoláda mliečna': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda horká': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda biela': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda orechová': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'bonbóny': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'žuvačky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'cukríky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'karamelky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené ovocie': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené banány': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené jablká': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'orechy': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy lieskové': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy vlašské': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy mandľové': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy kešu': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy pistácie': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka slnečnicové': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka tekvicové': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'popcorn': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy zemiakové': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy kukuričné': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'krekry': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušienky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušienky čokoládové': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'koláče': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'torty': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrzlina': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'zmrzlina vanilková': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'zmrzlina čokoládová': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'med': 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=400&h=400&fit=crop',
        'džem': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'džem jahodový': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'nutella': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'marmeláda': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sirup': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        
        # Frozen Foods - Very specific
        'zmrazené jahody': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené maliny': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené brokolica': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené karfiol': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené ryža': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené cestoviny': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené pizza': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené hranolky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené ryba': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené mäso': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené kuracie': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené zelenina mix': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené ovocie mix': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené špenát': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené hrášok': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené kukurica': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené brusnice': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené čučoriedky': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené čerešne': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrazené bobuľový mix': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        
        # Canned & Preserved - Very specific
        'paradajková omáčka 500g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'kečup 500g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'horčica 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'majonéza 400g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot vínny 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot jablkový 500ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'sojová omáčka 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'worcester omáčka 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'teriyaki omáčka 250ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'bbq omáčka 500g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'česneková pasta 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'zázvorová pasta 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'wasabi pasta 50g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'harissa pasta 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto bazalkové 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto česnekové 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'pesto rajčiakové 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'hummus 200g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'tahini pasta 250g': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'kokosové mlieko 400ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko mandľové 1l': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko sójové 1l': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko ovsené 1l': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'mlieko kokosové 400ml': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        
        # Beverages - Very specific
        'voda minerálna 1.5l': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'voda pramenitá 1.5l': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'džús jablkový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús pomarančový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús višňový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús jahodový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús ananasový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'džús grapefruitový 1l': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop',
        'čaj čierny 100g': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj zelený 100g': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj ovocný 100g': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'čaj bylinkový 100g': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
        'káva mletá 250g': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'káva instant 200g': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'káva bez kofeínu 200g': 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400&h=400&fit=crop',
        'kakao 200g': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'kakao instant 200g': 'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
        'cola 2l': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'sprite 2l': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'fanta 2l': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        'pivo svetlé 0.5l': 'https://images.unsplash.com/photo-1608270586620-248524c67de9?w=400&h=400&fit=crop',
        'pivo tmavé 0.5l': 'https://images.unsplash.com/photo-1608270586620-248524c67de9?w=400&h=400&fit=crop',
        'víno biele 0.75l': 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?w=400&h=400&fit=crop',
        'víno červené 0.75l': 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?w=400&h=400&fit=crop',
        'limonáda citrón 2l': 'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop',
        
        # Sweets & Snacks - Very specific
        'čokoláda mliečna 100g': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda horká 100g': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda biela 100g': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'čokoláda orechová 100g': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'bonbóny 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'žuvačky 100g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'cukríky 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'karamelky 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené ovocie 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené banány 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušené jablká 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'orechy 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy lieskové 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy vlašské 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy mandľové 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy kešu 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'orechy pistácie 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka slnečnicové 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'semienka tekvicové 200g': 'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
        'popcorn 100g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy 150g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy zemiakové 150g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'čipsy kukuričné 150g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'krekry 200g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušienky 300g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sušienky čokoládové 300g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'koláče 500g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'torty 1kg': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'zmrzlina 500ml': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'zmrzlina vanilková 500ml': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'zmrzlina čokoládová 500ml': 'https://images.unsplash.com/photo-1567206563064-6f60f40a2b57?w=400&h=400&fit=crop',
        'med 500g': 'https://images.unsplash.com/photo-1558642452-9d2a7deb7f62?w=400&h=400&fit=crop',
        'džem 400g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'džem jahodový 400g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'nutella 400g': 'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
        'marmeláda 400g': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
        'sirup 500ml': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
    }
    
    # Normalize keys and check for specific product matches first
    normalized_specific_images = {normalize_product_name(key): url for key, url in specific_images.items()}

    # Exact normalized match
    if name_lower in normalized_specific_images:
        return normalized_specific_images[name_lower]

    # Partial normalized match (longest keys first for best disambiguation)
    for key in sorted(normalized_specific_images.keys(), key=len, reverse=True):
        if key and key in name_lower:
            return normalized_specific_images[key]

    # Additional keyword-level fallbacks for wide product sets
    keyword_images = {
        'ketchup': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'horcica': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'majonéza': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'ocot': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&h=400&fit=crop',
        'vajcia': 'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
        'mleko': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
        'syr': 'https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?w=400&h=400&fit=crop',
        'jogurt': 'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop',
        'maslo': 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=400&h=400&fit=crop',
        'chlieb': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
        'cestoviny': 'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
        'ryza': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&h=400&fit=crop',
        'ovoce': 'https://images.unsplash.com/photo-1619566636858-adf2597f7335?w=400&h=400&fit=crop',
        'zelenina': 'https://images.unsplash.com/photo-1566385101042-1a0aa0c1268c?w=400&h=400&fit=crop',
        'mieso': 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
        'ryba': 'https://images.unsplash.com/photo-1535591273668-578e3116644?w=400&h=400&fit=crop',
        'mydlo': 'https://images.unsplash.com/photo-1582719478250-7f0f4f4cad41?w=400&h=400&fit=crop',
        'sampón': 'https://images.unsplash.com/photo-1582719478250-7f0f4f4cad41?w=400&h=400&fit=crop',
        'zubna pasta': 'https://images.unsplash.com/photo-1542831371-29b0f74f9713?w=400&h=400&fit=crop',
        'zabna kefka': 'https://images.unsplash.com/photo-1517821099605-8fbed0e0ffcc?w=400&h=400&fit=crop',
        'pracie prask': 'https://images.unsplash.com/photo-1583137096245-6b49ae143d22?w=400&h=400&fit=crop',
        'toaletny papier': 'https://images.unsplash.com/photo-1556228453-715733c16688?w=400&h=400&fit=crop',
    }
    for key, url in keyword_images.items():
        if key in name_lower:
            return url

    # Fall back to category image
    return category_images.get(category, 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&h=400&fit=crop')


def seed_products():
    """Seed the database with products if empty"""
    if Product.query.count() > 0:
        return  # Already seeded
    
    # Import the products list from scraper
    from pantry_pulse.selenium_scraper import PRODUCTS
    
    seeded_count = 0
    for product_name in PRODUCTS:
        if not Product.query.filter_by(name=product_name).first():
            category = get_product_category(product_name)
            product = Product(name=product_name, category=category)
            db.session.add(product)
            seeded_count += 1
    
    if seeded_count > 0:
        db.session.commit()
        logger.info(f'Seeded {seeded_count} products into database')

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
                product = Product(name=product_name, category=get_product_category(product_name))
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
    # Seed products if database is empty
    seed_products()
    
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

@app.route('/api/products')
def api_products():
    """API endpoint for searching and filtering products"""
    # Ensure products are seeded
    seed_products()
    
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    sort_by = request.args.get('sort', 'name')
    
    # Start with all products
    query = Product.query
    
    # Apply search filter
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))
    
    # Apply category filter
    if category:
        query = query.filter(Product.category == category)
    
    # Apply sorting
    if sort_by == 'price':
        # Sort by lowest average price
        query = query.outerjoin(PriceEntry).group_by(Product.id).order_by(db.func.avg(PriceEntry.price).asc())
    elif sort_by == 'newest':
        # Sort by most recently added
        query = query.order_by(Product.id.desc())
    else:  # name (default)
        query = query.order_by(Product.name.asc())
    
    products = query.all()
    
    # Build response
    response = {
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'category': p.category,
                'slug': p.name.lower().replace(' ', '-'),
                'image_url': get_product_image_url(p.name)
            }
            for p in products
        ],
        'count': len(products)
    }
    
    return jsonify(response)

@app.route('/api/categories')
def api_categories():
    """API endpoint to get all available categories"""
    # Ensure products are seeded
    seed_products()
    
    categories = db.session.query(Product.category).distinct().filter(Product.category != None).order_by(Product.category).all()
    return jsonify({
        'categories': [c[0] for c in categories if c[0]]
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info("Live Scraper App on http://127.0.0.1:5000")
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))

