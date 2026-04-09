# ─────────────────────────────────────────────────────────────────────────────
# Tiny-OpenClaw — Docker image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Install system deps needed by Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libx11-6 libx11-xcb1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir httpx python-dotenv "python-telegram-bot>=21.0" "playwright>=1.44.0"

# Install Playwright browser binary
RUN playwright install chromium

# Copy application code
COPY . .

# Runtime data volumes (sessions + memory survive container restarts)
VOLUME ["/app/SESSIONS.json", "/app/MEMORY.json"]

CMD ["python", "main.py"]
