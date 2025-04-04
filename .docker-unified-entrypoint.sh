#!/bin/bash
set -e

# Enhanced diagnostic logging
echo "===== DEPLOYMENT DIAGNOSTICS START ====="
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo "Environment: DOCKER_ENV=$DOCKER_ENV, DEBUG_STARTUP=$DEBUG_STARTUP"
echo "Log level: $LOGLEVEL"
echo "User: $(whoami), ID: $(id)"
echo "Current directory: $(pwd)"
echo "Directory listing:"
ls -la

# Add localhost entries
echo "Adding host entries..."
echo "127.0.0.1 localhost" >> /etc/hosts
echo "127.0.0.1 localhost.localdomain" >> /etc/hosts
echo "::1 localhost ip6-localhost ip6-loopback" >> /etc/hosts

# Create required directories if missing
echo "Creating required directories..."
mkdir -p /app/static/screenshots
mkdir -p /app/logs
mkdir -p /tmp/chromedriver
mkdir -p /tmp/chrome_user_data

# Ensure chromedriver directories exist with proper permissions
if [ "$SKIP_CHMOD" != "true" ]; then
    echo "Setting directory permissions..."
    if [ $(id -u) -eq 0 ]; then
        chmod -R 777 /tmp/chromedriver
        chmod -R 777 /tmp/chrome_user_data
        chmod -R 777 /app/logs
        chmod -R 777 /app/static/screenshots
        chmod -R 777 /usr/local/lib/python3.11/site-packages/chromedriver_autoinstaller
    else
        echo "Warning: Not running as root, skipping permissions"
    fi
fi

# Create notification sound file if missing
if [ ! -f /app/static/notification.mp3 ]; then
    echo "Creating a placeholder notification sound"
    touch /app/static/notification.mp3
fi

# Configure urllib3 connection pools
export PYTHONPATH=/app:$PYTHONPATH

# Create a Python startup file for urllib3 configuration
echo "Creating urllib3 configuration..."
cat > /app/urllib3_config.py << EOF
import urllib3
import logging
import os
import sys

# Print diagnostic information
print("Python version:", sys.version)
print("Python path:", sys.path)
print("Environment variables:", {k: v for k, v in os.environ.items() if not any(secret in k.lower() for secret in ['password', 'token', 'key', 'secret'])})

# Configure urllib3
pool_size = int(os.environ.get('URLLIB3_CONNECTIONPOOL_SIZE', '20'))
urllib3.PoolManager = lambda *args, **kwargs: urllib3.PoolManager(*args, maxsize=pool_size, **{k: v for k, v in kwargs.items() if k != 'maxsize'})

# Configure logging
logging_level = os.environ.get('LOGLEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, logging_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set more verbose logging for key components
for logger_name in ['TwitterBot', 'TwitterService', 'Scraper', 'TweetManager', 'Auth', 'Authenticator']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
# Add root logger handler to also output to stdout
root_logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger.addHandler(handler)
root_logger.info("Logging configured successfully")
EOF

export PYTHONSTARTUP=/app/urllib3_config.py

# Set Chrome options
echo "Configuring Chrome options..."
export HEADLESS_BROWSER="true"
export CHROME_NO_SANDBOX="true"
export CHROME_USER_DATA_DIR="/tmp/chrome_user_data"

# Configure web interface URLs
export NOTIFICATION_URL="http://localhost:5000/api/admin/notifications"
export INTERNAL_NOTIFICATION_URL="http://localhost:5000/api/admin/notifications"
export WEB_INTERFACE_HOST="localhost"
export WEB_INTERFACE_PORT="5000"
export WEB_INTERFACE_URL="http://localhost:5000"

# Check critical files and directories
echo "Checking for critical files:"
for file in unified_service.py requirements.txt; do
    if [ -f "$file" ]; then
        echo "✓ $file exists"
    else
        echo "✗ $file MISSING"
    fi
done

echo "Directory structure:"
find /app -maxdepth 2 -type d | sort

echo "===== DEPLOYMENT DIAGNOSTICS END ====="
echo "Unified service ready to start with command: $@"

# Execute the provided command
exec "$@" 