#!/usr/bin/env python3
"""
Run the PotravinyPulse Flask app.
Usage: python run.py
"""
from app import app, db
from loguru import logger

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Database tables created if not exist.")
    logger.info("Starting PotravinyPulse on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=app.config['DEBUG'])

