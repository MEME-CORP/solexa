# health_check.py - Basic health check endpoint for Render

from flask import Flask, jsonify
import threading
import logging
import os
import psutil

app = Flask(__name__)
logger = logging.getLogger('HealthCheck')

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint for Render"""
    try:
        # Get system resources
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/app/static')
        
        # Check if critical services are running
        thread_count = threading.active_count()
        
        return jsonify({
            'status': 'healthy',
            'threads': thread_count,
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent
            },
            'disk': {
                'total': disk.total,
                'free': disk.free,
                'percent': disk.percent
            }
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Start the Flask app for health checks
    app.run(host='0.0.0.0', port=5001) 