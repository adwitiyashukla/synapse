# Hugging Face Space image for Synapse.
#
# Single container: builds the React frontend, then serves it plus the FastAPI
# backend from one process on the Space port (7860).
#
# Notes specific to Spaces:
#   * the container runs as uid 1000, so everything is created under /home/user
#   * container disk is ephemeral, so SQLite and Chroma live in a writable
#     working directory and are re-seeded on each cold start
#   * GEMINI_API_KEY and SECRET_KEY arrive at runtime from Space secrets

# ---------- Stage 1: build the frontend ----------
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

COPY --chown=user backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user backend/app ./app
COPY --chown=user backend/demo_assets ./demo_assets
COPY --from=frontend-build --chown=user /build/dist ./static

RUN mkdir -p $HOME/app/data

# Public demo configuration. Secrets are injected by the Space at runtime.
ENV DEMO_MODE=true \
    DATABASE_URL=sqlite+aiosqlite:////home/user/app/data/synapse.db \
    CHROMA_DIR=/home/user/app/data/chroma \
    DEMO_SEED_DIR=/home/user/app/demo_assets \
    PORT=7860

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
