#!/bin/bash
set -e

# setup.sh - Prepares a RunPod instance for ApplyGenie
# Run this script to install Docker, start the Ollama container, and pull required models.

echo ">>> Starting ApplyGenie RunPod Setup..."

# 1. Update system and install basic dependencies
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common

# 2. Check if Docker is installed, install if missing
if ! command -v docker &> /dev/null
then
    echo ">>> Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
else
    echo ">>> Docker is already installed."
fi

# 3. Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null
then
    echo ">>> Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo ">>> Docker Compose is already installed."
fi

# 4. Create the Docker network if it doesn't exist
docker network inspect applygenie_network >/dev/null 2>&1 || \
    docker network create applygenie_network

# 5. Bring up the Ollama container via Docker Compose (assumes docker-compose.yml is in current dir)
echo ">>> Starting Ollama service..."
docker-compose up -d ollama

echo ">>> Waiting for Ollama API to be ready..."
until curl -s http://localhost:11434/api/tags >/dev/null; do
    sleep 2
done

# 6. Pull the required models
echo ">>> Pulling DeepSeek-R1 (32B)..."
docker exec -it deepseek_ollama ollama run deepseek-r1:32b --keepalive 5m "Testing deepseek-r1"

echo ">>> Pulling DeepSeek-VL2 (Tiny)..."
docker exec -it deepseek_ollama ollama run deepseek-vl2:tiny --keepalive 5m "Testing deepseek-vl2"

echo ">>> Pulling nomic-embed-text for any future RAG needs..."
docker exec -it deepseek_ollama ollama pull nomic-embed-text

echo ">>> Setup Complete! You can now run the main application stack with: docker-compose up -d applygenie"
