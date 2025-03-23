# src/frontend/routes.py

from flask import render_template, send_from_directory, request, jsonify, current_app
import os
import sys
from pathlib import Path
import glob
from src.ai_generator import AIGenerator

# Initialize the AI Generator
generator = AIGenerator(mode='twitter')

def init_app(app):
    """Initialize the Flask application with routes"""
    
    # Get absolute path to the frontend/build directory - using multiple methods for reliability
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(current_file_dir, 'build')
    
    # Extended debugging
    print("\n=============== DEBUGGING PATH RESOLUTION ===============")
    print(f"1. Current file: {__file__}")
    print(f"2. Absolute path of current file: {os.path.abspath(__file__)}")
    print(f"3. Directory of current file: {current_file_dir}")
    print(f"4. Build directory path: {build_dir}")
    
    # Check if build directory exists
    if not os.path.exists(build_dir):
        print(f"ERROR: Build directory not found at {build_dir}")
        print("Attempting to locate build directory...")
        
        # Try to find the build directory by searching
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"5. Project root: {project_root}")
        
        # Look for build directory in various likely locations
        possible_locations = [
            os.path.join(project_root, 'frontend', 'build'),
            os.path.join(project_root, 'build'),
            os.path.join(current_file_dir, '..', 'build'),
            os.path.join(current_file_dir, '..', 'frontend', 'build')
        ]
        
        for location in possible_locations:
            print(f"Checking location: {location}")
            if os.path.exists(location):
                build_dir = location
                print(f"Found build directory at: {build_dir}")
                break
        
        # If still not found, try a more aggressive search
        if not os.path.exists(build_dir):
            print("Still couldn't find build directory. Attempting recursive search...")
            for root, dirs, files in os.walk(project_root):
                if 'build' in dirs:
                    potential_build = os.path.join(root, 'build')
                    if os.path.exists(os.path.join(potential_build, 'index.html')):
                        build_dir = potential_build
                        print(f"Found build directory at: {build_dir}")
                        break
    
    # Set the static directory path
    static_dir = os.path.join(build_dir, 'static')
    
    # Print configuration and directory contents for debugging
    print(f"\nFinal build_dir: {build_dir}")
    print(f"Final static_dir: {static_dir}")
    print(f"Build directory exists: {os.path.exists(build_dir)}")
    print(f"Static directory exists: {os.path.exists(static_dir)}")
    
    # List contents to verify file structure
    if os.path.exists(build_dir):
        print("\nBuild directory contents:")
        for item in os.listdir(build_dir):
            print(f" - {item}")
            item_path = os.path.join(build_dir, item)
            if item == 'static' and os.path.isdir(item_path):
                print("  Static directory contents:")
                for subitem in os.listdir(item_path):
                    print(f"   - {subitem}")
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path):
                        print(f"     {subitem} contents:")
                        for file in os.listdir(subitem_path):
                            print(f"      - {file}")
    
    print("=============== END DEBUGGING ===============\n")
    
    # Serve static files directly using Flask's static_folder
    app.static_folder = static_dir
    app.static_url_path = '/static'
    
    # Serve the React app
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        # First, check if the path points to an existing file in build_dir
        file_path = os.path.join(build_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            directory, filename = os.path.split(file_path)
            return send_from_directory(directory, filename)
        
        # Fallback to index.html for client-side routing
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