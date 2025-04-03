# health_check.py - Basic health check endpoint for Render

from flask import Flask, Blueprint, jsonify
import threading
import logging
import os
import psutil

app = Flask(__name__)
logger = logging.getLogger('HealthCheck')

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'message': 'Solexa unified service is running'
    }), 200

if __name__ == '__main__':
    # Start the Flask app for health checks
    app.run(host='0.0.0.0', port=5001) 