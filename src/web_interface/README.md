# Web Interface for Multi-Platform AI Bot

This module provides a web-based interface for the Multi-Platform AI Bot, allowing users to generate platform-specific content using the bot's AI capabilities.

## Features

- User-friendly web interface for content generation
- Platform selection (Twitter/Telegram)
- Character counter with platform-specific limits
- Real-time content styling using the existing AI generators
- Preview of generated content

## Technical Details

- Built with Flask for backend functionality
- Pure HTML/CSS/JavaScript frontend (no external dependencies)
- Integrates with the existing AIGenerator for content styling
- RESTful API for content generation

## API Endpoints

### `/api/generate` (POST)

Generates styled content for the selected platform.

**Request Format:**
```json
{
  "message": "Your message content here",
  "platform": "twitter" // or "telegram"
}
```

**Response Format:**
```json
{
  "styled_content": "Generated content here",
  "platform": "twitter" // or "telegram"
}
```

## Usage

The web interface can be started using the main script with the `--bots web` flag:

```bash
python main.py --bots web --web-port 5000 --web-host 0.0.0.0
```

Optional parameters:
- `--web-port`: Port number (default: 5000)
- `--web-host`: Host address (default: 0.0.0.0)
- `--web-debug`: Enable Flask debug mode

## Integration

The web interface uses the same AIGenerator that powers the bot's other platforms, ensuring consistent styling across all interfaces.