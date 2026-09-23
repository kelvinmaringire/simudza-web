# Use Python 3.12 slim image
FROM python:3.12-slim-bookworm

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set workdir
WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update --yes --quiet && \
    apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    libffi-dev \
    libssl-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Install pip-tools for dependency management (optional but recommended)
RUN pip install --upgrade pip setuptools wheel

# Copy only requirements first (for better caching)
COPY requirements.txt .

# Use Docker’s build cache for pip downloads (do not set PIP_NO_CACHE_DIR —
# the cache mount lets pip resume large wheels after timeouts/DNS blips).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        --retries 15 \
        --resume-retries 20 \
        --default-timeout=100 \
        -r requirements.txt

# Copy the app source
COPY . .

# Expose Django port
EXPOSE 8000

# Start container (use sh to avoid needing chmod on host when .:/app is mounted)
CMD ["sh", "entrypoint.sh"]
