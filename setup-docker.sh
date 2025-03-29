#!/bin/bash
# This script prepares the environment for Docker containers

# Create directories with correct permissions
mkdir -p ./logs ./static/screenshots

# Ensure the permissions are relaxed enough
chmod -R 777 ./logs ./static/screenshots || echo "Warning: Could not set permissions (this is normal on some systems)"

# Check if .env file exists
if [ ! -f ./.env ]; then
    echo "Warning: No .env file found. Creating a template..."
    cat > ./.env << EOF
# Environment variables
FLASK_SECRET_KEY=change_this_to_a_random_string
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
TWITTER_EMAIL=your_twitter_email
OPENAI_API_KEY=your_openai_api_key
EOF
    echo "Please edit the .env file with your credentials before starting Docker"
fi

echo "Environment setup complete. Run 'docker-compose up' to start the services." 