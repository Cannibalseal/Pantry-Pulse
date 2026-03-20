import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'

    # Database configuration (supports DATABASE_URL for full connection strings)
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = os.environ.get('DB_PORT') or '3306'
    DB_NAME = os.environ.get('DB_NAME') or 'pantry_pulse'
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or ''

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, 'pantry_pulse.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{DEFAULT_SQLITE_PATH}"

    # TODO: For MySQL, uncomment below and setup server/DB
    # DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    # DB_PORT = os.environ.get('DB_PORT') or '3306'
    # DB_NAME = os.environ.get('DB_NAME') or 'pantry_pulse'
    # DB_USER = os.environ.get('DB_USER') or 'root'
    # DB_PASSWORD = os.environ.get('DB_PASSWORD') or ''
    # SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

