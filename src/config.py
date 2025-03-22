# src/config.py

import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger('config')

class Config:
    # API Keys
    GLHF_API_KEY = os.getenv('GLHF_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
    TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')
    TWITTER_EMAIL = os.getenv('TWITTER_EMAIL')

    # OpenAI Client
    openai_client = OpenAI(
        api_key=GLHF_API_KEY,
        base_url=os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')
    )

    # Bot Configuration
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'solexaprobot')
    DISCORD_BOT_USERNAME = os.getenv('DISCORD_BOT_USERNAME', 'Fwog-AI')

    # Model Configuration 1
    AI_MODEL = os.getenv('MODEL', 'deepseek-ai/DeepSeek-R1')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')

    # Model Configuration 2
    AI_MODEL2 = os.getenv('MODEL2',  'reissbaker/llama-3.1-70b-abliterated-lora')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')

    # Conversation Settings
    MAX_MEMORY = int(os.getenv('MAX_MEMORY', '2'))

    # Database Configuration
    SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    SUPABASE_KEY = os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

    # Blockchain Configuration
    TOKEN_MINT_ADDRESS = os.getenv('TOKEN_MINT_ADDRESS', 'DEFAULT_MINT_ADDRESS')
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
    
