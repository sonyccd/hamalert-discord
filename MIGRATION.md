# Migration Guide

## Upgrading from Previous Version

The refactored version maintains **100% backward compatibility** with existing deployments. No configuration changes are required.

### What's Changed (Internal)

The codebase has been refactored for better maintainability:
- Code split into modules (`config.py`, `formatters.py`, `utils.py`)
- Added type hints throughout
- Improved error handling with exponential backoff
- Added Discord rate limiting (30 messages/minute)

### What Stays the Same

✅ **All environment variables remain unchanged:**
- `USERNAME` - Your HamAlert username
- `PASSWORD` - Your HamAlert password  
- `WEBHOOK_URL` - Discord webhook URL
- `UPTIMEKUMA_URL` - Optional Uptime Kuma URL
- `HEARTBEAT_INTERVAL` - Heartbeat interval (default: 300)

✅ **All command-line arguments remain unchanged:**
- `--username`
- `--password`
- `--webhook`
- `--host`
- `--port`
- `--heartbeat-url`
- `--heartbeat-interval`
- `--log-level`

✅ **Docker usage remains unchanged:**
```bash
docker run -d \
  -e USERNAME=your_username \
  -e PASSWORD=your_password \
  -e WEBHOOK_URL=your_webhook_url \
  ghcr.io/sonyccd/hamalert-discord:latest
```

### Upgrading

1. **For Docker users:** Simply pull the latest image
   ```bash
   docker pull ghcr.io/sonyccd/hamalert-discord:latest
   docker restart your-container-name
   ```

2. **For direct Python users:** Pull the latest code
   ```bash
   git pull
   # No configuration changes needed!
   ```

### New Features

While maintaining backward compatibility, the refactored version adds:
- Automatic Discord rate limiting to prevent webhook abuse
- Better connection resilience with exponential backoff
- Improved error messages and logging
- Type safety throughout the codebase

### Testing the Upgrade

To verify your configuration still works:
```bash
# Test with your existing environment variables
python3 app.py --log-level DEBUG
```

The application should connect and start processing spots exactly as before.