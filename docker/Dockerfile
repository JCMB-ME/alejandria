# =============================================================================
# Alejandría — single multi-stage Dockerfile
# Stage 1: Build SvelteKit frontend
# Stage 2: Install Calibre CLI + Python deps
# Stage 3: Final runtime image
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Frontend build
# -----------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

# Copy package files first for better layer caching
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build


# -----------------------------------------------------------------------------
# Stage 2: Calibre installer (separation to maximize layer caching)
# -----------------------------------------------------------------------------
FROM debian:bookworm-slim AS calibre-installer

ARG CALIBRE_VERSION=7.13.0

# Calibre CLI install requires these dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xvfb \
        libgl1 \
        libglib2.0-0 \
        libnss3 \
        libxcomposite1 \
        libxrandr2 \
        libxdamage1 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Download and run Calibre installer (CLI mode)
RUN curl -fsSL https://download.calibre-ebook.com/linux-installer/x86_64.sh -o /tmp/calibre-installer.sh \
    && chmod +x /tmp/calibre-installer.sh \
    && /tmp/calibre-installer.sh --no-desktop --version=${CALIBRE_VERSION} \
    && rm /tmp/calibre-installer.sh


# -----------------------------------------------------------------------------
# Stage 3: Python backend deps
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS backend-builder

WORKDIR /build/backend

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Copy pyproject.toml
COPY backend/pyproject.toml ./
COPY backend/README.md ./

# Install dependencies (no dev deps for production)
RUN uv pip install --system --no-cache .

# Copy source
COPY backend/src ./src


# -----------------------------------------------------------------------------
# Stage 4: Final runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG TARGETARCH=amd64

LABEL org.opencontainers.image.title="Alejandría" \
      org.opencontainers.image.description="Self-hosted ebook library" \
      org.opencontainers.image.source="https://github.com/your-user/alejandria" \
      org.opencontainers.image.licenses="MIT"

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tini \
        gosu \
        libgl1 \
        libglib2.0-0 \
        libnss3 \
        libxcomposite1 \
        libxrandr2 \
        libxdamage1 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libfontconfig1 \
        libstdc++6 \
        fonts-noto \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Copy Calibre from installer stage
COPY --from=calibre-installer /opt/calibre /opt/calibre
ENV PATH="/opt/calibre:${PATH}"

# Copy Python packages
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY --from=backend-builder /build/backend/src /app/backend/src

# Copy frontend build
COPY --from=frontend-builder /build/frontend/build /app/frontend/build
COPY --from=frontend-builder /build/frontend/package.json /app/frontend/package.json

# Copy entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create non-root user (will be remapped via PUID/PGID at runtime)
RUN groupadd -g 1000 alejandria && \
    useradd -u 1000 -g 1000 -m -s /bin/bash alejandria && \
    mkdir -p /library /config && \
    chown -R alejandria:alejandria /library /config /app

# Working directory
WORKDIR /app

# Volumes
VOLUME ["/library", "/config"]

# Expose port
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Entry point
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["alejandria"]
