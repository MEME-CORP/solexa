from flask import Flask, render_template, send_from_directory, Blueprint
import os
from pathlib import Path

# Create a Blueprint for the frontend routes
frontend_bp = Blueprint('frontend', __name__, 
                       template_folder='templates',
                       static_folder='static')

@frontend_bp.route('/')
def index():
    """Serve the main frontend application"""
    return render_template('index.html')

# Optionally add API routes that your frontend will need
@frontend_bp.route('/api/tasks')
def get_tasks():
    """Get user tasks from the database"""
    # You can use your existing DatabaseService here
    from src.database.supabase_client import DatabaseService
    db = DatabaseService()
    # Example query - adjust based on your actual database schema
    tasks = db.client.table('tasks').select('*').execute()
    return tasks.data

@frontend_bp.route('/api/stats')
def get_stats():
    """Get user statistics"""
    # Example implementation
    return {
        "completed_tasks": 15,
        "points": 250,
        "level": 3
    }

def init_app(app):
    """Initialize the frontend blueprint with the main application"""
    # Register the blueprint with the app
    app.register_blueprint(frontend_bp, url_prefix='/ui')
    
    # Create directories if they don't exist
    current_dir = Path(__file__).parent
    os.makedirs(current_dir / 'templates', exist_ok=True)
    os.makedirs(current_dir / 'static' / 'css', exist_ok=True)
    os.makedirs(current_dir / 'static' / 'js', exist_ok=True)
    
    return app