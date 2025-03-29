#!/bin/bash
set -e

# Check for Python environment
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Display environment info
echo "Running in Docker environment: $DOCKER_ENV"
echo "Current working directory: $(pwd)"
echo "Files in current directory:"
ls -la

# Execute the provided command (likely python main.py --bots telegram)
exec "$@" 