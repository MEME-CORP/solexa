from flask import Flask, render_template, jsonify, request
import os
import sys
import logging
from pathlib import Path
import requests

# Add the project root to Python path to enable imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.ai_generator import AIGenerator
from src.config import Config
# Import the necessary Twitter components
from src.twitter_bot.scraper import Scraper
from src.twitter_bot.tweets import TweetManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web_interface')

app = Flask(__name__)
generator = AIGenerator(mode='twitter')  # For Twitter styling
telegram_generator = AIGenerator(mode='discord_telegram')  # For Telegram styling

# Store Twitter browser instance to prevent multiple initializations
twitter_scraper = None
tweet_manager = None

@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('social_media_writer.html')

@app.route('/api/generate', methods=['POST'])
def generate_styled_content():
    """Generate styled content for the selected platform."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        message = data.get('message', '')
        platform = data.get('platform', 'twitter')
        request_type = data.get('request_type', 'transform')  # Default to transform for the web UI
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
            
        logger.info(f"Processing {request_type} request for platform: {platform}")
        
        # Use the appropriate generator based on the platform and request type
        if platform == 'twitter':
            if request_type == 'transform':
                content = generator.transform_message(user_message=message)
            else:
                content = generator.generate_content(
                    user_message=message,
                    conversation_context='',
                    username='web_user'
                )
        else:  # telegram
            if request_type == 'transform':
                content = telegram_generator.transform_message(user_message=message)
            else:
                content = telegram_generator.generate_content(
                    user_message=message,
                    conversation_context='',
                    username='web_user'
                )
            
        logger.info(f"Generated/transformed content: {content[:100]}...")
        
        return jsonify({
            "styled_content": content,
            "platform": platform,
            "request_type": request_type
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route('/api/post_to_telegram', methods=['POST'])
def post_to_telegram():
    """Send a message to Telegram using the bot."""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        message = data.get('message', '')
        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400
        
        # Get Telegram configuration
        token = Config.TELEGRAM_BOT_TOKEN
        chat_id = Config.TELEGRAM_CHAT_ID  # From .env
        
        if not token or not chat_id:
            logger.error("Missing Telegram configuration (token or chat_id)")
            return jsonify({"success": False, "error": "Missing Telegram configuration"}), 500
        
        # Send message to Telegram
        logger.info(f"Sending message to Telegram chat {chat_id}")
        
        # Ensure chat_id is properly formatted (some chats require '@' prefix)
        # Try to convert to integer first for user IDs
        try:
            chat_id_int = int(chat_id)
            chat_id = chat_id_int
        except ValueError:
            # If not an integer, keep as string (might be a channel name)
            pass
            
        telegram_api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"  # Add support for basic formatting
        }
        
        # Add more debug info
        logger.info(f"Sending to Telegram API: {telegram_api_url}")
        logger.info(f"Using chat_id: {chat_id}, type: {type(chat_id)}")
        
        response = requests.post(telegram_api_url, json=payload)
        response_json = response.json()
        
        if response.status_code == 200:
            logger.info("Message sent to Telegram successfully")
            return jsonify({"success": True})
        else:
            error_msg = response_json.get('description', response.text)
            logger.error(f"Error sending message to Telegram: {error_msg}")
            
            # Provide more helpful error message
            if "chat not found" in error_msg:
                logger.error("The bot may not have been added to the chat or the chat ID is incorrect")
                return jsonify({
                    "success": False, 
                    "error": f"Chat not found. Please ensure the bot has been added to chat ID {chat_id} and has permission to send messages."
                }), 500
            else:
                return jsonify({"success": False, "error": error_msg}), 500
            
    except Exception as e:
        logger.error(f"Error posting to Telegram: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/post_to_twitter', methods=['POST'])
def post_to_twitter():
    """Send a message to Twitter using the bot."""
    global twitter_scraper, tweet_manager
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        message = data.get('message', '')
        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400
        
        logger.info(f"Initializing Twitter components for posting...")
        
        # Initialize Twitter components if not already initialized
        if twitter_scraper is None:
            twitter_scraper = Scraper(proxy=os.getenv("PROXY_URL"))
            initialization_success = twitter_scraper.initialize()
            
            if not initialization_success:
                if twitter_scraper.is_verification_screen():
                    logger.warning("Twitter verification required")
                    verification_success = twitter_scraper.handle_verification_screen()
                    if not verification_success:
                        return jsonify({
                            "success": False, 
                            "error": "Twitter verification required. Please check email for verification code."
                        }), 500
                else:
                    return jsonify({
                        "success": False, 
                        "error": "Failed to initialize Twitter components"
                    }), 500
            
            # Initialize tweet manager
            tweet_manager = TweetManager(twitter_scraper.driver)
        
        # Post tweet
        logger.info(f"Posting message to Twitter: {message[:50]}...")
        tweet_manager.send_tweet(message)
        
        logger.info("Message posted to Twitter successfully")
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Error posting to Twitter: {e}", exc_info=True)
        
        # Cleanup on error
        if twitter_scraper:
            try:
                twitter_scraper.close()
                twitter_scraper = None
                tweet_manager = None
            except:
                pass
                
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup_twitter', methods=['POST'])
def cleanup_twitter():
    """Clean up Twitter resources when finished."""
    global twitter_scraper, tweet_manager
    
    try:
        if twitter_scraper:
            logger.info("Cleaning up Twitter resources...")
            twitter_scraper.close()
            twitter_scraper = None
            tweet_manager = None
            return jsonify({"success": True})
        else:
            return jsonify({"success": True, "message": "No Twitter resources to clean up"})
    except Exception as e:
        logger.error(f"Error cleaning up Twitter resources: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask web server."""
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_web_server(debug=True)