# src/frontend/routes.py

from flask import render_template, send_from_directory, request, jsonify, current_app
import os
import sys
from pathlib import Path
from src.ai_generator import AIGenerator

# Initialize the AI Generator
generator = AIGenerator(mode='twitter')

def init_app(app):
    """Initialize the Flask application with routes"""
    
    # Get absolute path to the frontend/build directory
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_file_dir)
    build_dir = os.path.join(current_file_dir, 'build')
    
    # Check if build directory exists, if not search in common locations
    if not os.path.exists(build_dir):
        possible_locations = [
            os.path.join(project_root, 'frontend', 'build'),
            os.path.join(project_root, 'build'),
            os.path.join(current_file_dir, '..', 'build'),
            os.path.join(current_file_dir, '..', 'frontend', 'build'),
            os.path.join(project_root, 'static')
        ]
        
        for location in possible_locations:
            if os.path.exists(location) and os.path.isdir(location):
                build_dir = location
                break
    
    # Configure static folder for Flask
    app.static_folder = os.path.join(build_dir, 'static') if os.path.exists(os.path.join(build_dir, 'static')) else build_dir
    app.static_url_path = '/static'
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        """Serve React app or static files"""
        if path != "" and os.path.exists(os.path.join(build_dir, path)):
            return send_from_directory(build_dir, path)
            
        # For all other routes, serve the index.html
        return send_from_directory(build_dir, 'index.html')
    
    # API endpoint for content generation
    @app.route('/api/generate', methods=['POST'])
    def generate_content():
        """Generate styled content based on user input"""
        try:
            data = request.json
            message = data.get('message', '')
            platform = data.get('platform', 'twitter')
            
            # Validate input
            if not message:
                return jsonify({'error': 'Message is required'}), 400
                
            if platform not in ['twitter', 'telegram']:
                return jsonify({'error': 'Invalid platform'}), 400
            
            # Use the 'twitter' mode for Twitter, and 'discord' mode for Telegram
            mode = 'twitter' if platform == 'twitter' else 'discord'
            
            # Generate content using the AI generator
            styled_content = generator.generate_content(
                user_message=message,
                mode=mode
            )
            
            return jsonify({
                'styled_content': styled_content,
                'platform': platform
            })
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500