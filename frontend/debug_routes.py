# src/frontend/debug_routes.py

from flask import Flask, send_from_directory, request, jsonify, send_file
import os
import glob
import sys

def create_app():
    """Create and configure the Flask app with detailed debugging"""
    app = Flask(__name__, static_folder=None)
    
    # Enable debug mode
    app.debug = True
    
    # Find all possible locations for the build directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    possible_locations = [
        os.path.join(current_dir, 'build'),
        os.path.join(project_root, 'frontend', 'build'),
        os.path.join(project_root, 'build'),
        os.path.join(project_root, 'static'),
        os.path.join(current_dir, '..', 'build'),
        os.path.join(current_dir, '..', 'frontend', 'build')
    ]
    
    # Try to find the build directory
    build_dir = None
    for location in possible_locations:
        if os.path.exists(location) and os.path.isdir(location):
            if os.path.exists(os.path.join(location, 'index.html')):
                build_dir = location
                break
    
    # If build directory not found, create a simple index.html
    if not build_dir:
        print("WARNING: Build directory not found. Creating temporary solution.")
        temp_dir = os.path.join(current_dir, 'temp_build')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create a simple HTML file without external dependencies
        with open(os.path.join(temp_dir, 'index.html'), 'w') as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Simple Post Writer</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #121218;
                        color: white;
                        margin: 0;
                        padding: 20px;
                    }
                    .container {
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #1e1e26;
                        border-radius: 8px;
                    }
                    h1 {
                        text-align: center;
                        margin-bottom: 30px;
                        background: linear-gradient(to right, #9d4edd, #ff5baa);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    }
                    textarea {
                        width: 100%;
                        height: 120px;
                        background-color: #282836;
                        color: white;
                        border: 1px solid #444;
                        border-radius: 4px;
                        padding: 10px;
                        margin-bottom: 15px;
                        resize: none;
                    }
                    button {
                        width: 100%;
                        padding: 12px;
                        background: linear-gradient(to right, #9d4edd, #ff5baa);
                        color: white;
                        border: none;
                        border-radius: 25px;
                        cursor: pointer;
                        font-weight: bold;
                    }
                    button:hover {
                        opacity: 0.9;
                    }
                    .preview {
                        margin-top: 20px;
                        padding: 15px;
                        background-color: #282836;
                        border-radius: 8px;
                        white-space: pre-wrap;
                    }
                    .platform-selector {
                        display: flex;
                        margin-bottom: 15px;
                    }
                    .platform-button {
                        flex: 1;
                        padding: 10px;
                        text-align: center;
                        background-color: #282836;
                        color: #888;
                        cursor: pointer;
                    }
                    .platform-button.active {
                        background-color: #9d4edd;
                        color: white;
                    }
                    .platform-button:first-child {
                        border-radius: 25px 0 0 25px;
                    }
                    .platform-button:last-child {
                        border-radius: 0 25px 25px 0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Social Media Post Writer</h1>
                    <div class="platform-selector">
                        <div class="platform-button active" id="twitter-btn">Twitter</div>
                        <div class="platform-button" id="telegram-btn">Telegram</div>
                    </div>
                    <textarea id="message-input" placeholder="Write your post here..."></textarea>
                    <button id="generate-btn">Generate Styled Post</button>
                    <div class="preview" id="preview" style="display: none;"></div>
                </div>
                
                <script>
                    // Simple JavaScript for the form
                    document.addEventListener('DOMContentLoaded', function() {
                        const twitterBtn = document.getElementById('twitter-btn');
                        const telegramBtn = document.getElementById('telegram-btn');
                        const messageInput = document.getElementById('message-input');
                        const generateBtn = document.getElementById('generate-btn');
                        const preview = document.getElementById('preview');
                        
                        let currentPlatform = 'twitter';
                        
                        twitterBtn.addEventListener('click', function() {
                            twitterBtn.classList.add('active');
                            telegramBtn.classList.remove('active');
                            currentPlatform = 'twitter';
                        });
                        
                        telegramBtn.addEventListener('click', function() {
                            telegramBtn.classList.add('active');
                            twitterBtn.classList.remove('active');
                            currentPlatform = 'telegram';
                        });
                        
                        generateBtn.addEventListener('click', function() {
                            const message = messageInput.value.trim();
                            if (!message) {
                                alert('Please enter a message');
                                return;
                            }
                            
                            generateBtn.textContent = 'Generating...';
                            
                            fetch('/api/generate', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    message: message,
                                    platform: currentPlatform
                                })
                            })
                            .then(response => response.json())
                            .then(data => {
                                preview.textContent = data.styled_content || 'No content generated';
                                preview.style.display = 'block';
                                generateBtn.textContent = 'Generate Styled Post';
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                preview.textContent = 'Error generating content';
                                preview.style.display = 'block';
                                generateBtn.textContent = 'Generate Styled Post';
                            });
                        });
                    });
                </script>
            </body>
            </html>
            """)
        
        build_dir = temp_dir
    
    print(f"Using build directory: {build_dir}")
    
    # List files in the build directory for debugging
    print("Files in build directory:")
    for root, dirs, files in os.walk(build_dir):
        level = root.replace(build_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for file in files:
            print(f"{sub_indent}{file}")
    
    # Define debug route to check what directories exist
    @app.route('/debug/paths')
    def debug_paths():
        paths_info = {
            'current_dir': current_dir,
            'project_root': project_root,
            'build_dir': build_dir,
            'possible_locations': [
                {'path': loc, 'exists': os.path.exists(loc), 'is_dir': os.path.isdir(loc) if os.path.exists(loc) else False}
                for loc in possible_locations
            ],
            'static_files': []
        }
        
        # Check for static files
        if build_dir and os.path.exists(os.path.join(build_dir, 'static')):
            static_dir = os.path.join(build_dir, 'static')
            for root, dirs, files in os.walk(static_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), static_dir)
                    paths_info['static_files'].append(rel_path)
        
        return jsonify(paths_info)
    
    # Define static file route
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        static_dir = os.path.join(build_dir, 'static')
        if os.path.exists(static_dir):
            if os.path.exists(os.path.join(static_dir, filename)):
                return send_from_directory(static_dir, filename)
        
        # If static directory doesn't exist or file not found
        print(f"Static file not found: {filename}")
        print(f"Expected path: {os.path.join(static_dir, filename)}")
        return '', 404
    
    # Main routes to serve the React app
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path):
        # First check if the path points to a file
        if path:
            file_path = os.path.join(build_dir, path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_file(file_path)
        
        # Default to serving index.html
        return send_file(os.path.join(build_dir, 'index.html'))
    
    # API endpoint for content generation
    @app.route('/api/generate', methods=['POST'])
    def generate_content():
        try:
            data = request.json
            message = data.get('message', '')
            platform = data.get('platform', 'twitter')
            
            if not message:
                return jsonify({'error': 'Message is required'}), 400
                
            if platform not in ['twitter', 'telegram']:
                return jsonify({'error': 'Invalid platform'}), 400
            
            # Use hardcoded response for testing
            styled_content = f"This is a styled version of your message for {platform}: {message}"
            
            # Try to import AIGenerator if available
            try:
                from src.ai_generator import AIGenerator
                generator = AIGenerator(mode='twitter')
                mode = 'twitter' if platform == 'twitter' else 'discord'
                styled_content = generator.generate_content(
                    user_message=message,
                    mode=mode
                )
            except ImportError:
                print("AIGenerator not available, using dummy response")
            
            return jsonify({
                'styled_content': styled_content,
                'platform': platform
            })
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': str(e)}), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)