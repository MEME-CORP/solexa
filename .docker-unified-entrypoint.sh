#!/bin/bash
set -e

echo "=== Starting Unified Service Docker Container $(date) ==="
echo "Environment: DOCKER_ENV=$DOCKER_ENV"
echo "Log level: $LOGLEVEL"

# If DOCKER_DEBUG=true, print all environment variables (excluding credentials)
if [ "$DOCKER_DEBUG" = "true" ]; then
    echo "Environment variables:"
    env | grep -v -E 'PASSWORD|API_KEY|TOKEN|SECRET' | sort
fi

# Don't try to modify permissions if SKIP_CHMOD is set
if [ "$SKIP_CHMOD" != "true" ]; then
    # Ensure shared directories exist with proper permissions
    mkdir -p /app/static/screenshots
    mkdir -p /app/logs
    mkdir -p /tmp/chromedriver
    mkdir -p /tmp/chrome_user_data
    
    # Only try to set permissions if running as root
    if [ $(id -u) -eq 0 ]; then
        chmod -R 777 /tmp/chromedriver
        chmod -R 777 /tmp/chrome_user_data
        chmod -R 777 /app/logs
        chmod -R 777 /app/static/screenshots
    fi
fi

# Ensure chromedriver directories exist with proper permissions
mkdir -p /usr/local/lib/python3.11/site-packages/chromedriver_autoinstaller/134
chmod -R 777 /usr/local/lib/python3.11/site-packages/chromedriver_autoinstaller

# If we need to create notifications sound file
if [ ! -f /app/static/notification.mp3 ]; then
    echo "Creating a placeholder notification sound"
    touch /app/static/notification.mp3
fi

# Configure urllib3 connection pools
export PYTHONPATH=/app:$PYTHONPATH

# Set up pre-execution hook to configure urllib3 connection pool
export PYTHONSTARTUP=/app/urllib3_config.py

# Create a Python startup file to configure urllib3
cat > /app/urllib3_config.py << EOF
import urllib3
import logging
import os

# Configure urllib3
pool_size = int(os.environ.get('URLLIB3_CONNECTIONPOOL_SIZE', '20'))
urllib3.PoolManager = lambda *args, **kwargs: urllib3.PoolManager(*args, maxsize=pool_size, **{k: v for k, v in kwargs.items() if k != 'maxsize'})

# Configure detailed logging
logging_level = os.environ.get('LOGLEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, logging_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set more verbose logging for key components
for logger_name in ['TwitterBot', 'TwitterService', 'Scraper', 'TweetManager', 'Auth']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
EOF

# Set up Chrome options for all services
export HEADLESS_BROWSER="true"
export CHROME_NO_SANDBOX="true"
export CHROME_USER_DATA_DIR="/tmp/chrome_user_data"

# Print Chrome configuration
echo "Chrome configuration:"
echo "CHROME_BIN: $CHROME_BIN"
echo "CHROMEDRIVER_DIR: $CHROMEDRIVER_DIR"
echo "CHROMEDRIVER_PATH: $CHROMEDRIVER_PATH"
echo "CHROME_USER_DATA_DIR: $CHROME_USER_DATA_DIR"
echo "HEADLESS_BROWSER: $HEADLESS_BROWSER"

echo "Unified service ready to start with command: $@"

# Execute the provided command with exec to properly handle signals
exec "$@" 