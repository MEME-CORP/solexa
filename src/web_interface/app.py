from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, send_file
import os
import sys
import logging
from pathlib import Path
import requests
import functools
import time
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from logging.handlers import RotatingFileHandler
import threading
import json
import tempfile
import uuid
from health_check import health_bp

# Add the project root to Python path to enable imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.ai_generator import AIGenerator
from src.config import Config
# Import the TwitterService instead of direct scraper and tweet manager imports
from src.twitter_bot.twitter_service import twitter_service
from src.verification_manager import VerificationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web_interface')

app = Flask(__name__)

# Add Flask secret key from environment variable or use a default for development
app.secret_key = os.getenv("FLASK_SECRET_KEY", "3d6f45a5fc12445dbac2f59c3b6c7cb1d3c4a91764d5a788")

# Log a warning if using default secret key in production
if os.getenv("FLASK_ENV") == "production" and app.secret_key == "3d6f45a5fc12445dbac2f59c3b6c7cb1d3c4a91764d5a788":
    logger.warning("WARNING: Using default secret key in production environment. This is insecure!")

generator = AIGenerator(mode='twitter')  # For Twitter styling
telegram_generator = AIGenerator(mode='discord_telegram')  # For Telegram styling

# Add admin configuration
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv("ADMIN_PASSWORD", "admin123"))

# Decorator for admin-only routes
def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

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
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        message = data.get('message', '')
        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400
        
        logger.info(f"Using existing Twitter service for posting...")
        
        # Use the existing Twitter service from twitter_service module
        # Skip initialization if it's already initialized
        if not twitter_service.is_initialized():
            logger.info("Twitter service not initialized yet, initializing...")
            # Only initialize if not already initialized
            initialization_success = twitter_service.initialize(proxy_url=os.getenv("PROXY_URL"))
            
            if not initialization_success:
                # Check for verification if initialization failed
                if twitter_service.scraper and twitter_service.scraper.driver:
                    if twitter_service.scraper.is_verification_screen():
                        logger.warning("Twitter verification required")
                        verification_success = twitter_service.scraper.handle_verification_screen()
                        if not verification_success:
                            return jsonify({
                                "success": False, 
                                "error": "Twitter verification required. Please check email for verification code."
                            }), 500
                else:
                    return jsonify({
                        "success": False, 
                        "error": "Failed to initialize Twitter service"
                    }), 500
        else:
            logger.info("Using already initialized Twitter service")
        
        # Post tweet with higher priority (0) and source as "web_interface"
        success = twitter_service.send_tweet(message, priority=0, source="web_interface")
        
        if success:
            logger.info("Message posted to Twitter successfully")
            return jsonify({"success": True})
        else:
            logger.error("Failed to post message to Twitter")
            return jsonify({"success": False, "error": "Failed to post message"}), 500
        
    except Exception as e:
        logger.error(f"Error posting to Twitter: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup_twitter', methods=['POST'])
def cleanup_twitter():
    """Clean up Twitter resources when finished."""
    try:
        # Clean up the user data directory if it exists
        user_data_dir = os.environ.get("CHROME_USER_DATA_DIR")
        if user_data_dir and os.path.exists(user_data_dir):
            try:
                import shutil
                shutil.rmtree(user_data_dir, ignore_errors=True)
                logger.info(f"Cleaned up user data directory: {user_data_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up user data directory: {e}")
        
        return jsonify({"success": True, "message": "Twitter service cleaned up"})
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USER and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard page"""
    return render_template('admin_dashboard.html')

@app.route('/admin/verification')
@admin_required
def admin_verification_list():
    """List of pending verifications"""
    pending_verifications = VerificationManager.list_pending_verifications()
    return render_template('admin_verification_list.html', verifications=pending_verifications)

@app.route('/admin/verification/<verification_id>', methods=['GET', 'POST'])
@admin_required
def admin_verification_detail(verification_id):
    """Verification detail page"""
    verification = VerificationManager.get_verification(verification_id)
    
    if not verification:
        flash('Verification not found')
        return redirect(url_for('admin_verification_list'))
    
    if request.method == 'POST':
        verification_code = request.form.get('verification_code')
        
        if not verification_code:
            flash('Please enter a verification code')
        else:
            success = VerificationManager.submit_verification_code(verification_id, verification_code)
            
            if success:
                flash('Verification code accepted')
                return redirect(url_for('admin_verification_list'))
            else:
                flash('Verification code rejected or error occurred')
    
    return render_template('admin_verification_detail.html', 
                          verification=verification,
                          verification_id=verification_id)

@app.route('/api/admin/verifications')
@admin_required
def api_verifications():
    """API endpoint to get pending verifications"""
    try:
        # Clean up old verifications first
        VerificationManager.cleanup_old_verifications(max_age_hours=1)
        
        # Get pending verifications
        pending_verifications = VerificationManager.list_pending_verifications()
        
        # Log the data for debugging
        logger.info(f"Returning {len(pending_verifications)} pending verifications")
        return jsonify(pending_verifications)
    except Exception as e:
        logger.error(f"Error fetching verifications: {e}")
        return jsonify({}), 500

@app.route('/api/admin/verification/<verification_id>', methods=['POST'])
@admin_required
def api_submit_verification(verification_id):
    """API endpoint to submit verification code"""
    data = request.json
    if not data or 'code' not in data:
        return jsonify({"success": False, "error": "No verification code provided"}), 400
    
    verification_code = data['code']
    success = VerificationManager.submit_verification_code(verification_id, verification_code)
    
    return jsonify({"success": success})

@app.route('/setup-directories')
def setup_directories():
    """Ensure necessary directories exist."""
    os.makedirs(os.path.join(app.static_folder, 'screenshots'), exist_ok=True)
    return "Directories set up successfully"

with app.app_context():
    # Create necessary directories
    if not os.path.exists(os.path.join(app.static_folder, 'screenshots')):
        os.makedirs(os.path.join(app.static_folder, 'screenshots'), exist_ok=True)
        logger.info("Created screenshots directory")

# Setup file logging
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'web_interface.log'),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
logging.getLogger('web_interface').addHandler(file_handler)

def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask web server."""
    app.run(host=host, port=port, debug=debug)

# Add a background task to periodically reload verification data
def reload_verifications_periodically():
    """Periodically reload verification data from file"""
    while True:
        try:
            # Load latest verifications every 5 seconds
            VerificationManager._load_verifications()
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error in verification reload thread: {e}")
            time.sleep(10)  # Wait longer if there was an error

# Start the background thread when the app starts
verification_thread = threading.Thread(target=reload_verifications_periodically, daemon=True)
verification_thread.start()

# Add this route to handle notifications
@app.route('/api/admin/notifications', methods=['POST'])
def api_notifications():
    """API endpoint to receive notifications"""
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"success": False, "error": "No message provided"}), 400
        
        message = data['message']
        message_type = data.get('type', 'info')
        
        # Log the incoming notification for debugging
        logger.info(f"Received notification: {message} (type: {message_type})")
        
        # Store notification in a file for display in the admin panel
        notification_file = os.path.join(app.static_folder, 'notifications.json')
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(notification_file), exist_ok=True)
        
        # Load existing notifications
        notifications = []
        if os.path.exists(notification_file):
            try:
                with open(notification_file, 'r') as f:
                    notifications = json.load(f)
            except Exception as e:
                logger.error(f"Error loading notifications file: {e}")
        
        # Add new notification
        notifications.append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'type': message_type,
            'read': False
        })
        
        # Keep only the latest 50 notifications
        notifications = notifications[-50:]
        
        # Save notifications
        with open(notification_file, 'w') as f:
            json.dump(notifications, f)
        
        logger.info(f"Notification saved successfully: {message[:50]}...")
        return jsonify({"success": True})
    
    except Exception as e:
        logger.error(f"Error handling notification: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Then add this line in the Flask app initialization part
app.register_blueprint(health_bp)

@app.route('/health/notification', methods=['GET'])
def notification_health():
    """Test the notification system health"""
    try:
        # Create a test notification
        notification_file = os.path.join(app.static_folder, 'notifications.json')
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(notification_file), exist_ok=True)
        
        # Load existing notifications
        notifications = []
        if os.path.exists(notification_file):
            try:
                with open(notification_file, 'r') as f:
                    notifications = json.load(f)
            except Exception as e:
                logger.error(f"Error loading notifications file: {e}")
        
        # Add health check notification
        notifications.append({
            'timestamp': datetime.now().isoformat(),
            'message': 'Notification system health check',
            'type': 'info',
            'read': True
        })
        
        # Save notifications
        with open(notification_file, 'w') as f:
            json.dump(notifications, f)
        
        return jsonify({
            "status": "healthy",
            "message": "Notification system working correctly",
            "notification_file_exists": os.path.exists(notification_file),
            "notification_count": len(notifications)
        })
    
    except Exception as e:
        logger.error(f"Error in notification health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

# Add this route to handle different admin URL patterns
@app.route('/admin/')
@admin_required
def admin_dashboard_with_slash():
    """Admin dashboard page (with trailing slash)"""
    return render_template('admin_dashboard.html')

# Fix the verification_list route
@app.route('/admin/verification')
@admin_required
def admin_verification_list_redirect():
    """Redirect to verification list"""
    return redirect(url_for('admin_verification_list'))

@app.route('/admin/create-test-verification')
@admin_required
def create_test_verification():
    """Create a test verification for debugging"""
    try:
        from src.verification_manager import VerificationManager
        import time
        
        verification_id = f"verify_test_{int(time.time())}"
        VerificationManager.register_verification(
            verification_id=verification_id,
            screenshot_path="/static/screenshots/test.png",
            driver=None
        )
        
        flash(f"Test verification created with ID: {verification_id}")
        return redirect(url_for('admin_verification_list'))
    except Exception as e:
        logger.error(f"Error creating test verification: {e}")
        flash(f"Error creating test verification: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset-verifications')
@admin_required
def admin_reset_verifications():
    """Reset the verifications file in case of corruption"""
    try:
        from src.verification_manager import VerificationManager
        success = VerificationManager.reset_verifications_file()
        
        if success:
            flash('Verification file reset successfully')
        else:
            flash('Failed to reset verification file')
        
        return redirect(url_for('admin_verification_list'))
    except Exception as e:
        logger.error(f"Error resetting verification file: {e}")
        flash(f"Error: {str(e)}")
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    run_web_server(debug=True)