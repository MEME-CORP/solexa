# src/config.py

import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
import logging
from pathlib import Path

# Try to load .env file at startup
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

logger = logging.getLogger('config')

class Config:
    # API Keys
    GLHF_API_KEY = os.getenv('GLHF_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
    TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')
    TWITTER_EMAIL = os.getenv('TWITTER_EMAIL')

    # Safely get OPENAI_API_KEY with fallback
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Initialize OpenAI client only if we have a key
    if OPENAI_API_KEY:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
        )
    else:
        print("Warning: No OpenAI API key found, functionality may be limited")
        openai_client = None

    # Add these lines for Gemini configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')

    # Default models to use 
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

    # Bot Configuration
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'papayaelbot')
    DISCORD_BOT_USERNAME = os.getenv('DISCORD_BOT_USERNAME', 'Fwog-AI')

    # Model Configuration 1
    AI_MODEL = os.getenv('MODEL', 'hf:deepseek-ai/DeepSeek-V3')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')

    # Model Configuration 2
    AI_MODEL2 = os.getenv('MODEL2', 'hf:meta-llama/Llama-3.3-70B-Instruct')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')

    # Conversation Settings
    MAX_MEMORY = int(os.getenv('MAX_MEMORY', '2'))

    # Database Configuration
    SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    SUPABASE_KEY = os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

    # Blockchain Configuration
    TOKEN_MINT_ADDRESS = os.getenv('TOKEN_MINT_ADDRESS', 'pQrXnnRNJLMFFdcYo1fUueznSAwogbFkFcXJff8ZGFM')
    logging.info(f"Config loaded TOKEN_MINT_ADDRESS: {TOKEN_MINT_ADDRESS}")

    DEV_WALLET_ADDRESS = os.getenv('DEV_WALLET_ADDRESS', 'DEFAULT_DEV_WALLET')

    # S3 Storage Configuration
    SUPABASE_STORAGE_URL = os.getenv('SUPABASE_STORAGE_URL', 'https://yopeqymfapmhjlpwmle.supabase.co/storage/v1/s3')
    SUPABASE_BUCKET_NAME = os.getenv('SUPABASE_BUCKET_NAME', 'memories')

    # Initialize Supabase client with storage config
    @staticmethod
    def get_supabase_client():
        """
        Get Supabase client using environment variables
        """
        try:
            # Use the NEXT_PUBLIC_ prefixed variables from .env
            supabase_url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
            supabase_key = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
            
            if not supabase_url or not supabase_key:
                logger.error("Missing Supabase credentials in environment variables")
                raise ValueError("Missing Supabase credentials")
                
            logger.info(f"Connecting to Supabase at {supabase_url}")
            return create_client(supabase_url, supabase_key)
            
        except Exception as e:
            logger.error(f"Error creating Supabase client: {e}")
            raise

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '231399891')  # Default chat ID with env override capability
    
