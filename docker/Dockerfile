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
        python3 \
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

# Download and run Calibre installer (CLI mode).
# Calibre reorganized their downloads in 2025; the old
# /linux-installer/x86_64.sh URL now redirects to an HTML "previous
# releases" page. The current URL returns a single shell script that
# installs the matching arch (x86_64 under qemu on ARM hosts).
RUN curl -fsSL https://download.calibre-ebook.com/linux-installer.sh -o /tmp/calibre-installer.sh \
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
# Stage 3b: Playwright Chromium (separated for layer caching — only rebuilds
# if pyproject deps or PLAYWRIGHT_BROWSERS_PATH change)
# -----------------------------------------------------------------------------
FROM backend-builder AS playwright-installer
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
        libasound2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
       python -m playwright install chromium --with-deps
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers


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

# Copy Playwright browsers (chromium only)
COPY --from=playwright-installer /opt/playwright-browsers /opt/playwright-browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

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
