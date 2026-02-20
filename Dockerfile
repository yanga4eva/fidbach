# Use NVIDIA's PyTorch base image which has CUDA pre-installed for Ollama acceleration
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Prevent Python from writing .pyc files, enable unbuffered output, set timezone to avoid tzdata prompt
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    OLLAMA_MODELS=/workspace/ollama

# Install system dependencies required for Chromium, Xvfb, VNC, OpenCV, Python, and Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    unzip \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    fluxbox \
    xterm \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    libgl1 \
    fonts-liberation \
    xdg-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    python3.11 \
    python3.11-venv \
    python3-pip \
    pciutils \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome Browser
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Map python3 to python3.11 for consistency
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Create the working directory
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create VNC directory and Ollama data directory
RUN mkdir -p /root/.vnc /root/.ollama

# Copy the application code
COPY . /app

# Expose ports
# 8080: noVNC
# 8501: Streamlit
# 8000: FastAPI
# 11434: Ollama API
EXPOSE 8080 8501 8000 11434

# Copy the entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Start the application via the entrypoint script
CMD ["/usr/local/bin/docker-entrypoint.sh"]
