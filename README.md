# hamalert-discord

A Python service that monitors HamAlert telnet feeds and forwards amateur radio spot notifications to Discord webhooks. Supports SOTA (Summits on the Air) and POTA (Parks on the Air) alerts with special formatting.

## Features

- Real-time monitoring of HamAlert telnet feed
- Automatic Discord webhook notifications for radio spots
- Special formatting for SOTA and POTA activations
- Exponential backoff for connection reliability
- Optional Uptime Kuma heartbeat monitoring
- Docker support for easy deployment

## Installation

### Using Docker

```bash
docker pull ghcr.io/sonyccd/hamalert-discord:latest
docker run -d \
  -e USERNAME=your_hamalert_username \
  -e PASSWORD=your_hamalert_password \
  -e WEBHOOK_URL=your_discord_webhook_url \
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
python app.py --username YOUR_USERNAME --password YOUR_PASSWORD --webhook YOUR_WEBHOOK_URL
```

## Configuration

The application can be configured using environment variables or command-line arguments:

| Environment Variable | CLI Argument | Description | Required |
|---------------------|--------------|-------------|----------|
| `USERNAME` | `--username` | HamAlert username | Yes |
| `PASSWORD` | `--password` | HamAlert password | Yes |
| `WEBHOOK_URL` | `--webhook` | Discord webhook URL | Yes |
| `UPTIMEKUMA_URL` | `--heartbeat-url` | Uptime Kuma push URL | No |
| `HEARTBEAT_INTERVAL` | `--heartbeat-interval` | Heartbeat interval (seconds, default: 300) | No |

Additional CLI options:
- `--host`: HamAlert server (default: hamalert.org)
- `--port`: HamAlert port (default: 7300)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Discord Message Format

### SOTA Spots
```
🏔️ SOTA spotted: **K1ABC** on 14.250 SSB 2 minutes ago
Summit: Mount Example
```

### POTA Spots
```
🌳 POTA spotted: **K1XYZ** on 7.040 CW 5 minutes ago
Park: US-1234 Example National Park
https://pota.app/#/park/US-1234
```

### Regular Spots
```
spotted: **W1XYZ** on 3.573 CW 1 minute ago
```

## Development

### Running Tests

```bash
# Run all tests
python -m unittest discover

# Run with verbose output
python -m unittest discover -v
```

### Building Docker Image

```bash
docker build -t hamalert-discord .
```

## How It Works

1. Connects to HamAlert telnet server using provided credentials
2. Switches to JSON mode for structured data
3. Monitors incoming spot notifications
4. Formats messages based on spot source (SOTA, POTA, or regular)
5. Sends formatted messages to Discord webhook
6. Optionally sends heartbeat pings to Uptime Kuma for monitoring

## Requirements

- Python 3.9+
- `requests` library
- HamAlert account (free registration at https://hamalert.org)
- Discord webhook URL

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/sonyccd/hamalert-discord/issues) page.