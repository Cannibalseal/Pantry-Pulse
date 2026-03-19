from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from config import Config
from datetime import datetime
from loguru import logger

# Configure logging
logger.add("app.log", rotation="1 MB", level="INFO")

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Store {self.name} - {self.city}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f'<Product {self.name} ({self.category})>'

class PriceEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('price_entries', lazy=True))
    store = db.relationship('Store', backref=db.backref('price_entries', lazy=True))

    def __repr__(self):
        return f'<PriceEntry {self.product.name} @ {self.store.name}: {self.price}>'

@app.route('/')
def index():
    # Query latest price changes (e.g., most recent entries)
    latest_prices = PriceEntry.query.join(Product).join(Store).order_by(PriceEntry.timestamp.desc()).limit(10).all()
    logger.info(f"Queried {len(latest_prices)} latest price entries")
    return render_template('index.html', prices=latest_prices)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info("App started")
    app.run(debug=app.config['DEBUG'])

