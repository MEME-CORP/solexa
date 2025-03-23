# src/frontend/routes.py

from flask import send_from_directory, request, jsonify
import os
import sys
from pathlib import Path
from src.ai_generator import AIGenerator

# Initialize the AI Generator
generator = AIGenerator(mode='twitter')

def init_app(app):
    """Initialize the Flask application with routes"""
    
    # Get absolute path to various directories
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_file_dir))
    
    # Search for build directory in multiple locations
    possible_build_locations = [
        os.path.join(project_root, 'frontend', 'build'),
        os.path.join(project_root, 'build'),
        os.path.join(project_root, 'static'),
        os.path.join(current_file_dir, 'build')
    ]
    
    # Find the first valid build directory
    build_dir = None
    for location in possible_build_locations:
        if os.path.exists(location) and os.path.isdir(location):
            if os.path.exists(os.path.join(location, 'index.html')):
                build_dir = location
                break
    
    # If no build directory was found, use the static directory
    if not build_dir:
        build_dir = os.path.join(project_root, 'static')
        print(f"No valid build directory found. Using {build_dir}")
    else:
        print(f"Using build directory: {build_dir}")
    
    # Print debug information
    print(f"Current file: {__file__}")
    print(f"Project root: {project_root}")
    print(f"Build directory exists: {os.path.exists(build_dir)}")
    
    # List contents of build directory
    if os.path.exists(build_dir):
        print("Build directory contents:")
        for item in os.listdir(build_dir):
            print(f" - {item}")
            if item == 'static' and os.path.isdir(os.path.join(build_dir, item)):
                static_contents = os.listdir(os.path.join(build_dir, item))
                print(f"   Static contents: {static_contents}")
    
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
    
    # Define a simple route to serve all files from build directory
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        # Handle empty path - serve index.html
        if not path:
            return send_from_directory(build_dir, 'index.html')
        
        # Check if path exists directly in build directory
        if os.path.exists(os.path.join(build_dir, path)):
            return send_from_directory(build_dir, path)
        
        # Check if path exists in static directory
        static_dir = os.path.join(build_dir, 'static')
        if path.startswith('static/') and os.path.exists(os.path.join(build_dir, path[7:])):
            return send_from_directory(build_dir, path[7:])
        
        # Special handling for /static/ paths
        if path.startswith('static/'):
            file_path = path[7:]  # Remove 'static/' prefix
            if os.path.exists(os.path.join(static_dir, file_path)):
                return send_from_directory(static_dir, file_path)
        
        # If all checks fail, return index.html (for SPA client-side routing)
        return send_from_directory(build_dir, 'index.html')