# Use the official lightweight Python image.
FROM python:3.9-slim

# Ensure output is logged straight to the terminal without buffering.
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container.
WORKDIR /app

# Copy requirements and install dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY app.py config.py formatters.py utils.py qrz.py ./

# The application uses environment variables.
# You can pass these at runtime using docker run -e, or define defaults here.
# Required environment variables:
# ENV USERNAME=your_username
# ENV PASSWORD=your_password
# ENV WEBHOOK_URL=https://your.discord.webhook.url
# Optional environment variables:
# ENV QRZ_USERNAME=your_qrz_username
# ENV QRZ_PASSWORD=your_qrz_password
# ENV UPTIMEKUMA_URL=https://your.uptime.kuma.url
# ENV HEARTBEAT_INTERVAL=300

# Run the application.
CMD ["python", "app.py"]
