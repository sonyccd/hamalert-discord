# hamalert-discord
[![CI/CD Pipeline](https://github.com/sonyccd/hamalert-discord/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/sonyccd/hamalert-discord/actions/workflows/ci-cd.yml)
[![RARS Discord](https://uptime.thebazemores.net/api/badge/4/status)](https://uptime.thebazemores.net/status/rars)

A Python service that monitors HamAlert telnet feeds and forwards amateur radio spot notifications to Discord webhooks. Features QRZ.com integration for enhanced callsign information, special formatting for SOTA (Summits on the Air) and POTA (Parks on the Air) alerts, and intelligent health monitoring.

## Features

- **Real-time monitoring** of HamAlert telnet feed with automatic reconnection
- **QRZ.com integration** - Enhanced callsign display with operator names and clickable QRZ links
- **Smart caching** - 24-hour QRZ data caching to minimize API calls
- **Special formatting** for SOTA and POTA activations with emoji indicators
- **Intelligent heartbeat monitoring** - Only reports healthy when actually connected to HamAlert
- **Rate limiting** - Built-in Discord webhook rate limiting (30 messages/minute)
- **Robust error handling** - Exponential backoff and graceful failure recovery
- **Docker support** for easy deployment and scaling

## Installation

### Using Docker

```bash
docker pull ghcr.io/sonyccd/hamalert-discord:latest
docker run -d \
  -e USERNAME=your_hamalert_username \
  -e PASSWORD=your_hamalert_password \
  -e WEBHOOK_URL=your_discord_webhook_url \
  -e QRZ_USERNAME=your_qrz_username \
  -e QRZ_PASSWORD=your_qrz_password \
  -e UPTIMEKUMA_URL=your_uptime_kuma_push_url \
  -e LOG_LEVEL=INFO \
  ghcr.io/sonyccd/hamalert-discord:latest
```

### Local Installation

```bash
# Clone the repository
git clone https://github.com/sonyccd/hamalert-discord.git
cd hamalert-discord

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py --username YOUR_USERNAME --password YOUR_PASSWORD --webhook YOUR_WEBHOOK_URL --qrz-username YOUR_QRZ_USERNAME --qrz-password YOUR_QRZ_PASSWORD
```

## Configuration

The application can be configured using environment variables or command-line arguments:

### Required Configuration

| Environment Variable | CLI Argument | Description | Required |
|---------------------|--------------|-------------|----------|
| `USERNAME` | `--username` | HamAlert username | **Yes** |
| `PASSWORD` | `--password` | HamAlert password | **Yes** |
| `WEBHOOK_URL` | `--webhook` | Discord webhook URL | **Yes** |

### Optional Configuration

| Environment Variable | CLI Argument | Description | Default |
|---------------------|--------------|-------------|---------|
| `QRZ_USERNAME` | `--qrz-username` | QRZ.com username for enhanced callsign lookup | None |
| `QRZ_PASSWORD` | `--qrz-password` | QRZ.com password for enhanced callsign lookup | None |
| `UPTIMEKUMA_URL` | `--heartbeat-url` | Uptime Kuma push URL for health monitoring | None |
| `HEARTBEAT_INTERVAL` | `--heartbeat-interval` | Heartbeat interval in seconds | 300 |
| `LOG_LEVEL` | `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |

### Additional CLI Options:
- `--host`: HamAlert server (default: hamalert.org)
- `--port`: HamAlert port (default: 7300)

### QRZ.com Integration

The bot supports optional QRZ.com integration to enhance callsign display:

- **With QRZ credentials**: First name and callsign become a single clickable link to QRZ
  - Example: **[John W1ABC](https://www.qrz.com/db/W1ABC)**
- **Without QRZ credentials**: Callsigns are still clickable links to QRZ
  - Example: **[W1ABC](https://www.qrz.com/db/W1ABC)**

QRZ integration features 24-hour caching to minimize API calls and automatic session management.

## Discord Message Format

### SOTA Spots
```
🏔️ SOTA spotted: **[John W1ABC](https://www.qrz.com/db/W1ABC)** on 14.074 FT8 2 minutes ago
Summit: Mount Washington W1/NH-001
```

### POTA Spots
```
🌳 POTA spotted: **[Sarah K4XYZ](https://www.qrz.com/db/K4XYZ)** on 7.032 CW 5 minutes ago
Park: K-0123 [Great Smoky Mountains National Park](https://pota.app/#/park/K-0123)
```

### Regular Spots
```
spotted: **[Mike VK2DEF](https://www.qrz.com/db/VK2DEF)** on 21.074 FT8 1 minute ago
```

### Features Highlighted:
- **🏔️ / 🌳 Emoji indicators** for SOTA and POTA spots
- **Clickable operator links** combining first name and callsign to QRZ.com pages
- **Link preview suppression** for clean message display
- **Relative timestamps** showing "X minutes ago"
- **Enhanced park/summit information** with reference numbers
- **Clickable park names** linking directly to POTA app for park details

## Development

### Running Tests

The project includes comprehensive unit tests covering all functionality:

```bash
# Run all tests
python -m unittest discover

# Run with verbose output
python -m unittest discover -v

# Run specific test files
python -m unittest test_qrz
python -m unittest test_connection_handling
python -m unittest test_integration
```

**Test Coverage:**
- Core functionality (authentication, connection, message processing)
- QRZ.com API integration and caching
- Error handling and edge cases
- Connection status monitoring
- Discord webhook integration
- Complete end-to-end workflows

### Building Docker Image

```bash
docker build -t hamalert-discord .
```

## How It Works

1. **Connects to HamAlert** telnet server using provided credentials with automatic reconnection
2. **Switches to JSON mode** for structured data parsing
3. **Monitors incoming spot notifications** in real-time
4. **Enhances callsign information** via QRZ.com API lookup with smart caching
5. **Formats messages** based on spot source (SOTA, POTA, or regular) with emoji indicators
6. **Sends formatted messages** to Discord webhook with rate limiting
7. **Reports health status** to Uptime Kuma only when successfully connected to HamAlert

### Architecture
- **Modular design** with separate components for connection, formatting, and notification
- **Robust error handling** with exponential backoff and graceful degradation
- **Smart caching** to minimize external API calls
- **Type hints** throughout for better code clarity and maintainability

## Requirements

- **Python 3.9+**
- **Required Python packages**: `requests` (see `requirements.txt`)
- **HamAlert account** - Free registration at [hamalert.org](https://hamalert.org)
- **Discord webhook URL** - Create in your Discord server settings
- **QRZ.com account** (optional) - For enhanced callsign lookup with operator names

### Getting Started:
1. **Register at HamAlert.org** to get your username/password
2. **Create a Discord webhook** in your server's channel settings
3. **Sign up at QRZ.com** (optional) for enhanced callsign information
4. **Configure and run** the bot with your credentials

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/sonyccd/hamalert-discord/issues) page.
