# ---- BASE PYTHON IMAGE ----
FROM python:3.10-slim-bullseye

# ---- SYSTEM DEPENDENCIES ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    unzip \
    gnupg \
    fonts-liberation \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libpoppler-cpp-dev \
    libjpeg-dev \
    libappindicator3-1 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    xdg-utils \
    awscli \
    chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ---- ENVIRONMENT ----
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    CHROME_BIN=/usr/bin/chromium

# ---- WORKDIR ----
WORKDIR /app

# ---- COPY SOURCE ----
COPY . /app

# ---- INSTALL PYTHON DEPENDENCIES ----
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ---- PYTHONPATH ----
ENV PYTHONPATH="/app"

# ---- ENTRYPOINT ----
CMD ["python", "-X", "utf8", "-u", "pipeline/run_all.py"]
