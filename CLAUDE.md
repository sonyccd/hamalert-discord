# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python application that monitors HamAlert telnet feeds and forwards amateur radio spot notifications to Discord webhooks. It supports SOTA (Summits on the Air) and POTA (Parks on the Air) alerts with special formatting.

## Architecture

The application is organized into modular components:

### Core Modules
- **app.py**: Main application with three primary classes:
  - `TelnetListener`: Connects to HamAlert telnet server, handles authentication and message processing
  - `DiscordNotifier`: Sends messages to Discord webhooks with rate limiting
  - `HeartbeatService`: Background thread for Uptime Kuma monitoring

- **config.py**: Configuration management with `Config` dataclass that validates settings and handles environment variables

- **formatters.py**: Message formatting with `SpotFormatter` class that handles different spot types:
  - SOTA spots: Prefixed with 🏔️ emoji and summit information
  - POTA spots: Prefixed with 🌳 emoji and park references with pota.app links
  - Generic spots: Standard formatting

- **utils.py**: Utility functions including:
  - `exponential_backoff`: Decorator for automatic retry with exponential backoff
  - `RateLimiter`: Rate limiting decorator for API calls

### Key Features
- Type hints throughout for better code clarity
- Automatic reconnection with exponential backoff
- Discord webhook rate limiting (30 messages/minute)
- Telnet keepalive to maintain connection
- Graceful shutdown handling

## Development Commands

```bash
# Run tests
python -m unittest discover

# Run a specific test file
python -m unittest test_app

# Run the application locally
python app.py --username YOUR_USERNAME --password YOUR_PASSWORD --webhook YOUR_WEBHOOK_URL

# Build Docker image
docker build -t hamalert-discord .

# Run Docker container
docker run -e USERNAME=your_username -e PASSWORD=your_password -e WEBHOOK_URL=your_webhook_url hamalert-discord
```

## Environment Variables

The application accepts configuration through environment variables:
- `USERNAME`: HamAlert username (converted to uppercase internally)
- `PASSWORD`: HamAlert password
- `WEBHOOK_URL`: Discord webhook URL for notifications
- `UPTIMEKUMA_URL`: Optional Uptime Kuma push URL for heartbeat monitoring
- `HEARTBEAT_INTERVAL`: Heartbeat interval in seconds (default: 300)

## Testing Strategy

Tests use unittest with mocking for external dependencies (telnet, requests). Key test areas:
- Discord webhook posting (mocked requests)
- Telnet connection initialization and retry logic
- Message formatting for different spot sources (SOTA, POTA, generic)
- JSON payload processing and validation
- Heartbeat service operation