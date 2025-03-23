# main.py

import sys
import threading
import argparse
import os
from pathlib import Path
import signal
import asyncio
import time
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv
from src.ato_manager import ATOManager
from functools import partial
from src.announcement_broadcaster import AnnouncementBroadcaster
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Global variables for thread management
running = True
twitter_thread = None
telegram_thread = None
discord_thread = None
web_thread = None

def signal_handler(signum, frame):
    """Handle shutdown signals in main thread"""
    global running, twitter_thread, telegram_thread, discord_thread, web_thread
    print(f"\nReceived signal {signum}. Starting graceful shutdown...")
    running = False
    
    # Wait for threads to finish
    threads_to_check = [
        (twitter_thread, "Twitter bot"),
        (telegram_thread, "Telegram bot"),
        (discord_thread, "Discord bot"),
        (web_thread, "Web interface")
    ]
    
    for thread, name in threads_to_check:
        if thread and thread.is_alive():
            print(f"Waiting for {name} to shut down...")
            thread.join(timeout=30)
            if thread.is_alive():
                print(f"{name} shutdown timed out!")
    
    print("Main thread shutting down...")
    sys.exit(0)

def setup_signal_handlers():
    """Setup signal handlers in main thread"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def run_twitter_bot():
    global running
    from src.twitter_bot.twitter_bot import TwitterBot
    
    try:
        # Create bot instance without signal handlers since we're in a thread
        bot = TwitterBot(handle_signals=False)
        
        # Register with broadcaster
        AnnouncementBroadcaster.register_twitter_bot(bot)
        
        # Create an event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.run())
        except Exception as e:
            print(f"Twitter bot error: {e}")
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except Exception as e:
        print(f"Twitter bot error: {e}")
    finally:
        print("Twitter bot has stopped.")

def run_telegram_bot():
    """Run the Telegram bot in the main thread"""
    try:
        from src.telegram_bot.telegram_bot import TelegramBot
        
        # Create and setup bot
        bot = TelegramBot()
        application = bot.setup()
        
        # Register with broadcaster
        AnnouncementBroadcaster.register_telegram_bot(bot)
        
        print("Starting Telegram bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error in Telegram bot: {e}")

def run_discord_bot():
    """Run the Discord bot"""
    global running
    try:
        from src.discord_bot.discord_bot import DiscordBot
        
        # Create and setup bot
        bot = DiscordBot()
        print("Starting Discord bot...")
        bot.run_bot()
        
    except Exception as e:
        print(f"Error in Discord bot: {e}")
    finally:
        print("Discord bot has stopped.")

def run_web_interface(host='0.0.0.0', port=5000, debug=False):
    """Run the web interface"""
    global running
    try:
        from src.web_interface.app import run_web_server
        
        print(f"Starting web interface on http://{host}:{port}...")
        run_web_server(host=host, port=port, debug=debug)
        
    except Exception as e:
        print(f"Error in web interface: {e}")
    finally:
        print("Web interface has stopped.")

async def initialize_ato_manager():
    """Initialize ATO Manager after 5 minute delay"""
    try:
        print("Waiting 5 minutes before initializing ATO Manager...")
        await asyncio.sleep(2)  # 5 minutes delay
        
        print("Initializing ATO Manager...")
        ato_manager = ATOManager()
        await ato_manager.initialize()
        print("ATO Manager initialized successfully")
        
    except Exception as e:
        print(f"Error initializing ATO Manager: {e}")

def run_ato_manager():
    """Run the ATO manager in its own thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_ato_manager())
    finally:
        loop.close()

def setup_paths():
    """Setup correct paths for loading config files"""
    # Add project root to Python path
    project_root = Path(__file__).parent
    sys.path.append(str(project_root))
    
    # Ensure prompts_config directory exists
    prompts_config_path = project_root / 'src' / 'prompts_config'
    if not prompts_config_path.exists():
        prompts_config_path.mkdir(parents=True, exist_ok=True)
        print(f"Created prompts_config directory at: {prompts_config_path}")

def main():
    setup_paths()
    
    global twitter_thread, discord_thread, web_thread, running
    parser = argparse.ArgumentParser()
    parser.add_argument('--bots', nargs='+', 
                      choices=['twitter', 'telegram', 'discord', 'ato', 'web'], 
                      help='Specify which bots to run')
    parser.add_argument('--web-port', type=int, default=5000,
                      help='Port for the web interface')
    parser.add_argument('--web-host', type=str, default='0.0.0.0',
                      help='Host for the web interface')
    parser.add_argument('--web-debug', action='store_true',
                      help='Run web interface in debug mode')
    args = parser.parse_args()

    if not args.bots:
        parser.print_help()
        return

    setup_signal_handlers()

    try:
        # Start ATO manager if specifically requested
        if 'ato' in args.bots and len(args.bots) == 1:
            print("Starting ATO Manager only...")
            run_ato_manager()
            return

        # Start requested bots
        if 'twitter' in args.bots:
            twitter_thread = threading.Thread(target=run_twitter_bot, daemon=True)
            twitter_thread.start()
            print("Twitter bot thread started.")

        if 'discord' in args.bots:
            discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
            discord_thread.start()
            print("Discord bot thread started.")
            
        if 'web' in args.bots:
            web_thread = threading.Thread(
                target=run_web_interface,
                args=(args.web_host, args.web_port, args.web_debug),
                daemon=True
            )
            web_thread.start()
            print(f"Web interface thread started on http://{args.web_host}:{args.web_port}")

        # Start ATO manager thread if any bot is running
        if any(bot in args.bots for bot in ['twitter', 'telegram', 'discord', 'web']):
            ato_thread = threading.Thread(target=run_ato_manager, daemon=True)
            ato_thread.start()
            print("ATO Manager thread scheduled (5 minute delay)...")

        if 'telegram' in args.bots:
            # Run Telegram bot in main thread
            run_telegram_bot()
        else:
            # Keep main thread alive for other bots
            while running:
                time.sleep(1)

    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        running = False
        print("Initiating shutdown sequence...")

        if twitter_thread and twitter_thread.is_alive():
            print("Waiting for Twitter bot to shut down...")
            twitter_thread.join(timeout=30)
            if twitter_thread.is_alive():
                print("Twitter bot shutdown timed out!")

        if discord_thread and discord_thread.is_alive():
            print("Waiting for Discord bot to shut down...")
            discord_thread.join(timeout=30)
            if discord_thread.is_alive():
                print("Discord bot shutdown timed out!")
                
        if web_thread and web_thread.is_alive():
            print("Waiting for Web interface to shut down...")
            web_thread.join(timeout=30)
            if web_thread.is_alive():
                print("Web interface shutdown timed out!")

        print("Main thread shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()