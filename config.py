# config.py - Flask application configuration
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Flask application configuration"""
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # API configuration
    API_PREFIX = '/api'
    
    # CORS settings
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']