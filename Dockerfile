##############################################
# Stage 1: Build frontend
##############################################
FROM node:22-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

##############################################
# Stage 2: Python backend + serve frontend
##############################################
FROM python:3.13-slim AS backend

# System deps for Playwright chromium — use playwright install-deps for completeness
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    libxshmfence1 libxfixes3 libx11-xcb1 libxcb1 libxext6 libx11-6 \
    libdbus-1-3 libglib2.0-0 libexpat1 \
    fonts-liberation wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Playwright browsers + all system deps
RUN uv run playwright install --with-deps chromium

# Copy backend code
COPY backend/ backend/

# Copy built frontend into static dir
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Data volume for SQLite + FB session
VOLUME /app/data
ENV DB_PATH=/app/data/sniper.db
ENV FB_STATE_PATH=/app/data/fb_state.json

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
