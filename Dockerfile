# ─────────────────────────────
# 🐳 Base Python image
# ─────────────────────────────
FROM python:3.10-slim-bullseye

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
    && apt-get clean

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
CMD ["python", "pipeline/run_scraper.py", "--source", "jasper", "--limit", "1"]
