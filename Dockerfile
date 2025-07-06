FROM python:3.10-slim

# Install system packages
COPY apt.txt /apt.txt
RUN apt-get update && xargs -a /apt.txt apt-get install -y && rm -rf /var/lib/apt/lists/*

# Set environment for Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY ott_bot.py .

# Start the bot
CMD ["python", "ott_bot.py"]
