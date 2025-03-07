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
COPY app.py .

# The application uses environment variables (HAMALERT_USERNAME, HAMALERT_PASSWORD, HAMALERT_WEBHOOK_URL).
# You can pass these at runtime using docker run -e, or define defaults here.
# For example:
# ENV HAMALERT_USERNAME=your_username
# ENV HAMALERT_PASSWORD=your_password
# ENV HAMALERT_WEBHOOK_URL=https://your.discord.webhook.url

# Run the application.
CMD ["python", "app.py"]
