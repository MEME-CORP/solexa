#!/bin/bash
set -e

echo "=== Starting Twitter Bot Docker Container $(date) ==="
echo "Environment: DOCKER_ENV=$DOCKER_ENV"
echo "Log level: $LOGLEVEL"

# If DOCKER_DEBUG=true, print all environment variables (excluding credentials)
if [ "$DOCKER_DEBUG" = "true" ]; then
    echo "Environment variables:"
    env | grep -v -E 'PASSWORD|API_KEY|TOKEN|SECRET' | sort
fi

# Skip chmod operations that might fail
if [ "$SKIP_CHMOD" != "true" ]; then
    # Ensure shared directories exist - but don't try to chmod them
    mkdir -p /app/static/screenshots || true
    mkdir -p /app/logs || true
    mkdir -p /tmp/chromedriver || true
fi

# Set a unique user data directory for the Twitter bot
export CHROME_USER_DATA_DIR="/app/internal/chrome_data_twitter"
mkdir -p $CHROME_USER_DATA_DIR || true
chmod -R 777 $CHROME_USER_DATA_DIR || true

# If we need to create notifications sound file
if [ ! -f /app/static/notification.mp3 ]; then
    echo "Creating a placeholder notification sound"
    # This would normally be a real sound file
    touch /app/static/notification.mp3 || true
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

# Run the command - this should be "python main.py --bots twitter"
echo "Starting $@ with PYTHONPATH=$PYTHONPATH"
exec "$@" 