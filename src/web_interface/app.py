from flask import Flask, render_template, jsonify, request
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path to enable imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.ai_generator import AIGenerator
from src.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web_interface')

app = Flask(__name__)
generator = AIGenerator(mode='twitter')  # For Twitter styling
telegram_generator = AIGenerator(mode='discord_telegram')  # For Telegram styling

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
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
            
        logger.info(f"Generating styled content for platform: {platform}")
        
        # Use the appropriate generator based on the platform
        if platform == 'twitter':
            content = generator.generate_content(
                user_message=message,
                conversation_context='',
                username='web_user'
            )
        else:  # telegram
            content = telegram_generator.generate_content(
                user_message=message,
                conversation_context='',
                username='web_user'
            )
            
        logger.info(f"Generated content: {content[:100]}...")
        
        return jsonify({
            "styled_content": content,
            "platform": platform
        })
        
    except Exception as e:
        logger.error(f"Error generating content: {e}", exc_info=True)
        return jsonify({"error": f"Error generating content: {str(e)}"}), 500

def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """Run the Flask web server."""
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run_web_server(debug=True)