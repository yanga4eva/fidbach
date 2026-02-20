#!/bin/bash
set -e

# Default settings
export DISPLAY=${DISPLAY:-:99}
export VNC_PASSWORD=${VNC_PASSWORD:-applygenie2026}
export VNC_RESOLUTION=${VNC_RESOLUTION:-1920x1080x24}
# Extract just the geometry WxH
export SCREEN_GEOMETRY=$(echo "$VNC_RESOLUTION" | cut -d'x' -f1,2)

echo ">>> Starting Xvfb on Display $DISPLAY with resolution $VNC_RESOLUTION..."
Xvfb $DISPLAY -screen 0 $VNC_RESOLUTION -ac -r &
XVFB_PID=$!
sleep 2

echo ">>> Starting Fluxbox Window Manager..."
fluxbox &
FLUXBOX_PID=$!

echo ">>> Setting up X11VNC Password..."
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASSWORD" /root/.vnc/passwd

echo ">>> Starting X11VNC..."
x11vnc -display $DISPLAY -usepw -forever -shared -bg -listen localhost -rfbport 5900
sleep 2

echo ">>> Starting web-based noVNC on port 8080..."
# websockify takes connections from 8080 and proxies to local 5900 via the noVNC index page
websockify --web /usr/share/novnc 8080 localhost:5900 &
NOVNC_PID=$!
sleep 2

echo ">>> Starting FastAPI application (Background)..."
# Start the FastAPI orchestrator/webhook service
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 1 &
FASTAPI_PID=$!

echo ">>> Starting Streamlit UI (Foreground)..."
# Start Streamlit on port 8501. It runs in the foreground, keeping the container alive.
streamlit run app/ui/dashboard.py

# Keep script running if streamlit dies for some reason
wait $XVFB_PID
