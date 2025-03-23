#!/usr/bin/env python
"""
Run script to start the Flask app with the React frontend
"""

import os
import sys
from pathlib import Path
import shutil

# Get the project root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir  # Modify this if the run script is in a subdirectory

# Add the project root to Python path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Check if necessary directory structure exists
src_dir = os.path.join(project_root, 'src')
if not os.path.exists(src_dir):
    os.makedirs(src_dir, exist_ok=True)
    print(f"Created src directory at {src_dir}")

src_frontend_dir = os.path.join(src_dir, 'frontend')
if not os.path.exists(src_frontend_dir):
    os.makedirs(src_frontend_dir, exist_ok=True)
    print(f"Created src/frontend directory at {src_frontend_dir}")

# Create the static directory if it doesn't exist
static_dir = os.path.join(project_root, 'static')
if not os.path.exists(static_dir):
    os.makedirs(os.path.join(static_dir, 'css'), exist_ok=True)
    os.makedirs(os.path.join(static_dir, 'js'), exist_ok=True)
    print(f"Created static directories at {static_dir}")

# Create __init__.py files for proper module resolution
for init_path in [
    os.path.join(src_dir, '__init__.py'),
    os.path.join(src_frontend_dir, '__init__.py')
]:
    if not os.path.exists(init_path):
        with open(init_path, 'w') as f:
            f.write('# Initialize package\n')
        print(f"Created {init_path}")

# Copy the routes.py file into src/frontend if needed
frontend_routes = os.path.join(project_root, 'frontend', 'routes.py')
src_frontend_routes = os.path.join(src_frontend_dir, 'routes.py')
if os.path.exists(frontend_routes) and not os.path.exists(src_frontend_routes):
    shutil.copy2(frontend_routes, src_frontend_routes)
    print(f"Copied routes.py to {src_frontend_routes}")

# Create debug_routes.py in the src/frontend directory if it doesn't exist
debug_routes_path = os.path.join(src_frontend_dir, 'debug_routes.py')
if not os.path.exists(debug_routes_path):
    with open(debug_routes_path, 'w') as f:
        f.write('''
from flask import Flask
import os
from pathlib import Path

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Configure static and template folders
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    static_dir = os.path.join(project_root, 'static')
    
    app.static_folder = static_dir
    app.template_folder = static_dir
    
    # Import and initialize routes
    from src.frontend.routes import init_app
    init_app(app)
    
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
''')
    print(f"Created debug_routes.py at {debug_routes_path}")

# Create a simple index.html file in the static directory if it doesn't exist
index_path = os.path.join(static_dir, 'index.html')
if not os.path.exists(index_path):
    with open(index_path, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Social Media Post Writer</title>
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
            color: #9d4edd;
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
            background-color: #9d4edd;
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
</html>""")
    print(f"Created index.html at {index_path}")

# Run the Flask app
try:
    print("Starting Flask debug server...")
    # Add src to path explicitly again to make extra sure
    sys.path.insert(0, src_dir)
    from src.frontend.debug_routes import create_app
    app = create_app()
    app.run(debug=True, port=5000)
except ImportError as e:
    print(f"Error importing Flask app: {e}")
    print("Please ensure Flask is installed (pip install flask)")
    print(f"Python path: {sys.path}")
    sys.exit(1)