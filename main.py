# main.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
try:
    from flask import Flask
    flask_available = True
except ImportError:
    flask_available = False
    print("Warning: Flask is not installed. Web UI will not be available.")
from src.ato_manager import ATOManager
from functools import partial
from src.announcement_broadcaster import AnnouncementBroadcaster
from datetime import datetime
from frontend.routes import init_app as init_frontend

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Global variables for thread management
running = True
twitter_thread = None
telegram_thread = None
discord_thread = None
flask_thread = None

def signal_handler(signum, frame):
    """Handle shutdown signals in main thread"""
    global running, twitter_thread, telegram_thread, discord_thread, flask_thread
    print(f"\nReceived signal {signum}. Starting graceful shutdown...")
    running = False
    
    # Wait for threads to finish
    threads_to_check = [
        (twitter_thread, "Twitter bot"),
        (telegram_thread, "Telegram bot"),
        (discord_thread, "Discord bot"),
        (flask_thread, "Flask web application")
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

def run_flask_app():
    """Run the Flask web application"""
    global running
    if not flask_available:
        print("Cannot start Flask application: Flask is not installed.")
        print("Install Flask with: pip install flask")
        return
        
    try:
        # Only import the frontend routes when we're actually going to use Flask
        try:
            from frontend.routes import init_app as init_frontend
            
            # Get absolute paths for directories
            current_dir = os.path.dirname(os.path.abspath(__file__))
            build_dir = os.path.abspath(os.path.join(current_dir, 'frontend', 'build'))
            static_dir = os.path.abspath(os.path.join(build_dir, 'static'))
            
            # Very detailed logging for debugging
            print("\n======== FLASK CONFIGURATION ========")
            print(f"Current directory: {current_dir}")
            print(f"Build directory: {build_dir}")
            print(f"Static directory: {static_dir}")
            print(f"Build dir exists: {os.path.exists(build_dir)}")
            print(f"Static dir exists: {os.path.exists(static_dir)}")
            
            # List build directory contents
            if os.path.exists(build_dir):
                print("\nBuild directory contents:")
                for item in os.listdir(build_dir):
                    print(f"  {item}")
            else:
                # Create the build directory if it doesn't exist
                os.makedirs(build_dir, exist_ok=True)
                print(f"Created build directory at {build_dir}")
            
            # Create static directory if it doesn't exist
            if not os.path.exists(static_dir):
                os.makedirs(static_dir, exist_ok=True)
                print(f"Created static directory at {static_dir}")
                
                # Create a test static file
                with open(os.path.join(static_dir, 'test.js'), 'w') as f:
                    f.write('console.log("Static file loaded successfully!");')
                print("Created test.js static file")
            
            # Create a basic index.html if it doesn't exist
            index_path = os.path.join(build_dir, 'index.html')
            if not os.path.exists(index_path):
                print(f"index.html not found, creating a basic one at {index_path}")
                
                # Create basic index.html with a script that tests static file loading
                with open(index_path, 'w') as f:
                    f.write('''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Test App</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center;
            margin-top: 50px;
        }
    </style>
</head>
<body>
    <h1>Test Page</h1>
    <p>If you can see this, Flask is serving HTML correctly.</p>
    
    <!-- This will test if static files are being served -->
    <script>
        fetch('/static/test.js')
            .then(response => {
                if (response.ok) {
                    document.body.innerHTML += '<p style="color:green">Static JS files work!</p>';
                } else {
                    document.body.innerHTML += '<p style="color:red">Static JS files not found (404)</p>';
                }
            })
            .catch(error => {
                document.body.innerHTML += '<p style="color:red">Error fetching static file: ' + error.message + '</p>';
            });
    </script>
</body>
</html>''')
            
            print("\n====================================")
            
            # Create Flask app with the correct configuration
            app = Flask(__name__, 
                        template_folder=build_dir,
                        static_folder=static_dir,
                        static_url_path='/static')
            
            # Initialize the frontend with the Flask app
            init_frontend(app)
            
            # Run the Flask app
            print("Starting Flask web application...")
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            
        except ImportError as e:
            print(f"Failed to import frontend routes: {e}")
            print("Make sure Flask is installed: pip install flask")
            return
        
    except Exception as e:
        print(f"Error in Flask application: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        print("Flask application has stopped.")

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
    
    global twitter_thread, discord_thread, flask_thread, running
    parser = argparse.ArgumentParser()
    parser.add_argument('--bots', nargs='+', 
                       choices=['twitter', 'telegram', 'discord', 'ato', 'web'], 
                       help='Specify which bots to run')
    parser.add_argument('--web', action='store_true', 
                        help='Start the web UI')
    args = parser.parse_args()

    if not args.bots and not args.web:
        parser.print_help()
        return

    setup_signal_handlers()

    try:
        # Start ATO manager if specifically requested
        if args.bots and 'ato' in args.bots and len(args.bots) == 1:
            print("Starting ATO Manager only...")
            run_ato_manager()
            return

        # Start requested bots
        if args.bots and 'twitter' in args.bots:
            twitter_thread = threading.Thread(target=run_twitter_bot, daemon=True)
            twitter_thread.start()
            print("Twitter bot thread started.")

        if args.bots and 'discord' in args.bots:
            discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
            discord_thread.start()
            print("Discord bot thread started.")

        # Start web UI if requested
        if (args.web or (args.bots and 'web' in args.bots)) and flask_available:
            flask_thread = threading.Thread(target=run_flask_app, daemon=True)
            flask_thread.start()
            print("Web UI thread started.")
        elif args.web or (args.bots and 'web' in args.bots):
            print("Web UI requested but Flask is not installed. Install Flask with: pip install flask")

        # Start ATO manager thread if any bot is running
        if args.bots and any(bot in args.bots for bot in ['twitter', 'telegram', 'discord', 'web']):
            ato_thread = threading.Thread(target=run_ato_manager, daemon=True)
            ato_thread.start()
            print("ATO Manager thread scheduled (5 minute delay)...")

        if args.bots and 'telegram' in args.bots:
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

        if flask_thread and flask_thread.is_alive():
            print("Waiting for Web UI to shut down...")
            flask_thread.join(timeout=30)
            if flask_thread.is_alive():
                print("Web UI shutdown timed out!")

        print("Main thread shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()
