from flask import Flask, send_from_directory
import os
import sys

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, static_folder=None)
    
    # Get absolute path to various directories
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_file_dir))
    
    print("\n=== DEBUG APPLICATION PATHS ===")
    print(f"Current file directory: {current_file_dir}")
    print(f"Project root: {project_root}")
    
    # Import and initialize routes after setting paths
    from src.frontend.routes import init_app
    init_app(app)
    
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
