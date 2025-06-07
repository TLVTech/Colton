# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory inside the container
# All subsequent commands will be relative to /app
WORKDIR /app

# Install system dependencies required by some Python libraries
# Specifically, cairosvg and Pillow often need these for image processing.
# --no-install-recommends makes the installation leaner.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2-dev \
    libjpeg-dev \
    libgif-dev \
    libxml2-dev \
    libffi-dev \
    # Clean up apt caches to keep the image size down
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install Python packages specified in requirements.txt
# --no-cache-dir helps reduce the image size.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project files (including all subdirectories) into the container at /app
COPY . .

# Define environment variables for internal paths, if needed by your scripts.
# (Your OPENAI_API_KEY will be provided via the mounted .env file at runtime).
ENV RESULTS_DIR=/app/results
ENV IMAGES_DIR=/app/results/images
ENV WATERMARK_PATH=/app/data/raw/group.png 
# Path to your watermark image inside the container