#!/usr/bin/env python3
"""
Run the PotravinyPulse Flask app.
Usage: python run.py
"""
import os

from pantry_pulse.app import app, db
from loguru import logger

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Database tables created if not exist.")

    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    logger.info(f"Starting PotravinyPulse on http://{host}:{port}")
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))

