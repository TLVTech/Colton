# ─────────────────────────────
# 🐳 Base Python image
# ─────────────────────────────
FROM python:3.10-slim-bullseye

# ─────────────────────────────
# 🌐 Install & generate a UTF-8 locale
# ─────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends locales --fix-missing \
    && sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# ─────────────────────────────
# 🌐 Force UTF-8 for Python I/O
# ─────────────────────────────
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# ─────────────────────────────
# 🧰 Install OS dependencies
# ─────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libpoppler-cpp-dev \
    libjpeg-dev \
    curl \
    unzip \
    gnupg \
    chromium \
    chromium-driver \
    fonts-liberation \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────
# 🏗 Set working directory
# ─────────────────────────────
WORKDIR /app

# ─────────────────────────────
# 📁 Copy source code
# ─────────────────────────────
COPY . /app

# ─────────────────────────────
# 📦 Install Python dependencies
# ─────────────────────────────
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ─────────────────────────────
# 🧭 Add /app to Python path
# ─────────────────────────────
ENV PYTHONPATH="/app"

# ─────────────────────────────
# 🏃 Default run command (can be overridden)
# ─────────────────────────────
#   -X utf8    -> force Python’s UTF-8 mode
#   -u         -> unbuffered stdout/stderr (helps logs appear in real time)
CMD ["python", "-X", "utf8", "-u", "pipeline/run_scraper.py", "--source", "jasper", "--limit", "1"]
