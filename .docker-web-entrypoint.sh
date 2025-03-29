#!/bin/bash
set -e

echo "=== Starting Web Interface Docker Container $(date) ==="
echo "Environment: DOCKER_ENV=$DOCKER_ENV"
echo "Log level: $LOGLEVEL"

# If DOCKER_DEBUG=true, print all environment variables (excluding credentials)
if [ "$DOCKER_DEBUG" = "true" ]; then
    echo "Environment variables:"
    env | grep -v -E 'PASSWORD|API_KEY|TOKEN|SECRET' | sort
fi

# Ensure shared directories exist
mkdir -p /app/static/screenshots || true
mkdir -p /app/logs || true
mkdir -p /tmp/chromedriver || true

# Explicitly set temporary directory permissions
chmod -R 777 /tmp/chromedriver || true

# Ensure chromedriver directories exist with proper permissions
mkdir -p /usr/local/lib/python3.11/site-packages/chromedriver_autoinstaller/134 || true
chmod -R 777 /usr/local/lib/python3.11/site-packages/chromedriver_autoinstaller || true

# Create shared temporary directory for chrome user data
export CHROME_TEMP_DIR="/tmp/chrome_user_data"
mkdir -p $CHROME_TEMP_DIR || true
chmod -R 777 $CHROME_TEMP_DIR || true

# Set Chrome options for Docker
export HEADLESS_BROWSER="true"
export CHROME_NO_SANDBOX="true"
export CHROME_USER_DATA_DIR="$CHROME_TEMP_DIR/web_interface"

# Configure urllib3 connection pools
export PYTHONPATH=/app:$PYTHONPATH

# Print Chrome configuration
echo "Chrome configuration:"
echo "CHROME_BIN: $CHROME_BIN"
echo "CHROMEDRIVER_DIR: $CHROMEDRIVER_DIR"
echo "CHROMEDRIVER_PATH: $CHROMEDRIVER_PATH"
echo "CHROME_USER_DATA_DIR: $CHROME_USER_DATA_DIR"
echo "HEADLESS_BROWSER: $HEADLESS_BROWSER"

echo "Web interface ready to start"

# Execute main.py with web interface parameters
exec "$@" 